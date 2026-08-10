"""Assignment and submission endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import enrich, models, security
from ..database import get_db
from ..deps import get_current_user
from ..schemas import AssignmentCreate, GradeRequest, SubmissionCreate

router = APIRouter(tags=["assignments"])


@router.get("/assignments")
def list_assignments(
    course_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    rows = db.scalars(select(models.Assignment)).all()

    if course_id:
        rows = [a for a in rows if a.course_id == course_id]
    elif user.role == "student":
        ids = set(enrich.student_course_ids(db, user.user_id))
        rows = [a for a in rows if a.course_id in ids]
    elif user.role == "lecturer":
        my_courses = {
            c.course_id
            for c in db.scalars(
                select(models.Course).where(models.Course.lecturer_id == user.user_id)
            ).all()
        }
        rows = [a for a in rows if a.course_id in my_courses]

    out = [enrich.assignment_dict(db, a) for a in rows]
    out.sort(key=lambda a: security.parse_iso(a["deadline"]) or 0)
    return out


@router.post("/assignments")
def create_assignment(
    body: AssignmentCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    if user.role == "student":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not permitted")

    course = db.get(models.Course, body.course_id)
    a = models.Assignment(
        assignment_id=security.uid("a"),
        course_id=body.course_id,
        course_code=course.course_code if course else None,
        title=body.title,
        instructions=body.instructions or "",
        deadline=body.deadline,
        max_score=int(body.max_score or 100),
        created_at=security.now_iso(),
    )
    db.add(a)
    enrich.audit(db, user, "assignment.create", a.title)
    for e in db.scalars(
        select(models.Enrolment).where(
            models.Enrolment.course_id == body.course_id,
            models.Enrolment.status == "active",
        )
    ).all():
        enrich.notify(
            db,
            e.student_id,
            type="assignment",
            title=f"New assignment: {course.course_code if course else ''}",
            body=f"{a.title} is due soon.",
        )
    db.commit()
    return enrich.assignment_dict(db, a)


@router.get("/assignments/{assignment_id}/submissions")
def list_submissions(assignment_id: str, db: Session = Depends(get_db)):
    rows = db.scalars(
        select(models.Submission).where(
            models.Submission.assignment_id == assignment_id
        )
    ).all()
    return [enrich.submission_dict(s) for s in rows]


@router.post("/assignments/{assignment_id}/submit")
def submit_assignment(
    assignment_id: str,
    body: SubmissionCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    a = db.get(models.Assignment, assignment_id)
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assignment not found")

    now = security.epoch_ms(security.now_iso()) or 0
    deadline = security.epoch_ms(a.deadline)
    late = deadline is not None and now > deadline

    existing = db.scalar(
        select(models.Submission).where(
            models.Submission.assignment_id == assignment_id,
            models.Submission.student_id == user.user_id,
        )
    )
    if existing:
        existing.file_name = body.file_name
        existing.submitted_at = security.now_iso()
        existing.late = late
        existing.score = None
        existing.feedback = None
        existing.graded_at = None
        enrich.audit(db, user, "assignment.resubmit", a.title)
        db.commit()
        return enrich.submission_dict(existing)

    sub = models.Submission(
        submission_id=security.uid("s"),
        assignment_id=assignment_id,
        student_id=user.user_id,
        student_name=user.full_name,
        file_key=f"subs/{security.uid('f')}",
        file_name=body.file_name,
        score=None,
        feedback=None,
        submitted_at=security.now_iso(),
        graded_at=None,
        late=late,
    )
    db.add(sub)
    enrich.audit(db, user, "assignment.submit", a.title)

    course = db.get(models.Course, a.course_id) if a.course_id else None
    lecturer_id = course.lecturer_id if course else user.user_id
    enrich.notify(
        db,
        lecturer_id,
        type="assignment",
        title="New submission",
        body=f"{user.full_name} submitted {a.title}.",
    )
    db.commit()
    return enrich.submission_dict(sub)


@router.post("/submissions/{submission_id}/grade")
def grade_submission(
    submission_id: str,
    body: GradeRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    if user.role == "student":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not permitted")

    sub = db.get(models.Submission, submission_id)
    if not sub:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Submission not found")

    sub.score = body.score
    sub.feedback = body.feedback or ""
    sub.graded_at = security.now_iso()
    enrich.audit(db, user, "assignment.grade", sub.submission_id)
    enrich.notify(
        db,
        sub.student_id,
        type="assignment",
        title="Assignment graded",
        body=f"You scored {sub.score} on a submission.",
    )
    db.commit()
    return enrich.submission_dict(sub)
