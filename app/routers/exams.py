"""Exam / CBT endpoints."""
from __future__ import annotations

import random

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import enrich, models, security
from ..database import get_db
from ..deps import get_current_user
from ..schemas import AttemptSave, AttemptSubmit, ExamCreate, ViolationReport

router = APIRouter(tags=["exams"])


@router.get("/exams")
def list_exams(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    rows = db.scalars(select(models.Exam)).all()

    if user.role == "student":
        ids = set(enrich.student_course_ids(db, user.user_id))
        rows = [e for e in rows if e.course_id in ids]
    elif user.role == "lecturer":
        my_courses = {
            c.course_id
            for c in db.scalars(
                select(models.Course).where(models.Course.lecturer_id == user.user_id)
            ).all()
        }
        rows = [e for e in rows if e.course_id in my_courses]

    strip = user.role == "student"
    return [enrich.exam_dict(e, strip_answers=strip) for e in rows]


@router.get("/exams/{exam_id}")
def get_exam(
    exam_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    e = db.get(models.Exam, exam_id)
    if not e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Exam not found")
    return enrich.exam_dict(e, strip_answers=(user.role == "student"))


@router.post("/exams")
def create_exam(
    body: ExamCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    if user.role == "student":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not permitted")

    course = db.get(models.Course, body.course_id)
    questions = []
    for q in body.questions or []:
        questions.append(
            {
                "question_id": q.question_id or security.uid("q"),
                "prompt": q.prompt,
                "options": q.options,
                "correct_answer": q.correct_answer,
                "points": q.points,
            }
        )
    e = models.Exam(
        exam_id=security.uid("x"),
        course_id=body.course_id,
        course_code=course.course_code if course else None,
        title=body.title,
        duration_minutes=int(body.duration_minutes or 20),
        start_time=body.start_time or security.now_iso(),
        end_time=body.end_time or security.iso_in_days(1),
        shuffle=body.shuffle is not False,
        questions=questions,
        status=body.status or "scheduled",
        stream=body.stream,
        schedule_type=body.schedule_type,
        screen_capture_enabled=body.screen_capture_enabled is not False,
    )
    db.add(e)
    enrich.audit(db, user, "exam.create", e.title)
    db.commit()
    return enrich.exam_dict(e)


@router.post("/exams/{exam_id}/attempts/start")
def start_attempt(
    exam_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    e = db.get(models.Exam, exam_id)
    if not e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Exam not found")

    now = security.epoch_ms(security.now_iso()) or 0
    end = security.epoch_ms(e.end_time)
    if e.status == "closed" or (end is not None and now > end):
        raise HTTPException(status.HTTP_409_CONFLICT, "This exam is closed")

    existing = db.scalar(
        select(models.ExamAttempt).where(
            models.ExamAttempt.exam_id == e.exam_id,
            models.ExamAttempt.student_id == user.user_id,
            models.ExamAttempt.status == "in_progress",
        )
    )
    if existing:
        return {
            "attempt": enrich.attempt_dict(existing),
            "exam": enrich.exam_dict(e, strip_answers=True),
            "recovered": True,
        }

    order = [q["question_id"] for q in (e.questions or [])]
    if e.shuffle:
        random.shuffle(order)

    attempt = models.ExamAttempt(
        attempt_id=security.uid("att"),
        exam_id=e.exam_id,
        student_id=user.user_id,
        student_name=user.full_name,
        started_at=security.now_iso(),
        submitted_at=None,
        score=None,
        answers={},
        question_order=order,
        status="in_progress",
        last_saved_at=security.now_iso(),
    )
    db.add(attempt)
    enrich.audit(db, user, "exam.attempt.start", e.title)
    db.commit()
    return {
        "attempt": enrich.attempt_dict(attempt),
        "exam": enrich.exam_dict(e, strip_answers=True),
        "recovered": False,
    }


@router.get("/exams/{exam_id}/attempts/me")
def my_attempt(
    exam_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    attempt = db.scalar(
        select(models.ExamAttempt).where(
            models.ExamAttempt.exam_id == exam_id,
            models.ExamAttempt.student_id == user.user_id,
        )
    )
    return enrich.attempt_dict(attempt) if attempt else None


@router.patch("/attempts/{attempt_id}")
def save_attempt(
    attempt_id: str,
    body: AttemptSave,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    a = db.get(models.ExamAttempt, attempt_id)
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attempt not found")
    if a.status != "in_progress":
        return enrich.attempt_dict(a)
    merged = dict(a.answers or {})
    merged.update({str(k): v for k, v in (body.answers or {}).items()})
    a.answers = merged
    a.last_saved_at = security.now_iso()
    db.commit()
    return {"ok": True, "last_saved_at": a.last_saved_at}


@router.post("/attempts/{attempt_id}/submit")
def submit_attempt(
    attempt_id: str,
    body: AttemptSubmit,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    a = db.get(models.ExamAttempt, attempt_id)
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attempt not found")
    exam = db.get(models.Exam, a.exam_id)

    if a.status != "in_progress":
        return {"attempt": enrich.attempt_dict(a), "score": a.score}

    if body.answers:
        merged = dict(a.answers or {})
        merged.update({str(k): v for k, v in body.answers.items()})
        a.answers = merged

    score = 0
    total = 0
    for q in (exam.questions or []):
        total += q.get("points", 0)
        if a.answers.get(q["question_id"]) == q.get("correct_answer"):
            score += q.get("points", 0)
    a.score = score
    a.submitted_at = security.now_iso()
    a.status = "auto_submitted" if body.auto else "submitted"
    enrich.audit(db, user, "exam.attempt.submit", exam.title if exam else a.exam_id)
    db.commit()
    return {"attempt": enrich.attempt_dict(a), "score": score, "total": total}


@router.get("/exams/{exam_id}/attempts")
def list_attempts(exam_id: str, db: Session = Depends(get_db)):
    rows = db.scalars(
        select(models.ExamAttempt).where(models.ExamAttempt.exam_id == exam_id)
    ).all()
    return [enrich.attempt_dict(a) for a in rows]


@router.post("/attempts/{attempt_id}/violations")
def report_violation(
    attempt_id: str,
    body: ViolationReport,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    a = db.get(models.ExamAttempt, attempt_id)
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attempt not found")
    if a.status != "in_progress":
        return enrich.attempt_dict(a)

    violations = list(a.violations or [])
    violations.append({"type": body.type, "timestamp": body.timestamp})
    a.violations = violations
    a.violation_count = len(violations)
    db.commit()
    return {"ok": True, "violation_count": a.violation_count}
