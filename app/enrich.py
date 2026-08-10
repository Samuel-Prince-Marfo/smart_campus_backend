"""Enrichment helpers and shared domain logic.

Every function here returns plain dicts/values shaped exactly like the frontend's
TypeScript interfaces, plus the small set of cross-cutting helpers (audit logging,
notifications, enrolment derivation, active academic period) used by the routers.
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .security import now_iso, uid


# ---------------------------------------------------------------------------
# Settings / active academic period
# ---------------------------------------------------------------------------
DEFAULT_SETTINGS: Dict[str, Any] = {
    "rotate_seconds": 15,
    "geofence_radius_m": 120,
    "totp_grace": True,
    "allow_self_register": True,
    "active_year": "2025/2026",
    "active_semester": 1,
}


def get_settings_row(db: Session) -> models.AppSetting:
    row = db.get(models.AppSetting, 1)
    if row is None:
        row = models.AppSetting(id=1, data=dict(DEFAULT_SETTINGS))
        db.add(row)
        db.flush()
    return row


def get_settings(db: Session) -> Dict[str, Any]:
    return dict(get_settings_row(db).data)


def active_period(db: Session) -> Dict[str, Any]:
    s = get_settings(db)
    semester = 2 if int(s.get("active_semester", 1)) == 2 else 1
    return {"academic_year": str(s.get("active_year", "2025/2026")), "semester": semester}


# ---------------------------------------------------------------------------
# Audit + notifications
# ---------------------------------------------------------------------------
def audit(db: Session, actor: models.User, action: str, target: str) -> None:
    log = models.AuditLog(
        log_id=uid("l"),
        actor_id=actor.user_id,
        actor_name=actor.full_name,
        action=action,
        target=target,
        ip_address=f"10.12.{random.randint(0, 30)}.{random.randint(0, 250)}",
        timestamp=now_iso(),
    )
    db.add(log)


def notify(db: Session, user_id: str, *, type: str, title: str, body: str) -> None:
    db.add(
        models.Notification(
            notification_id=uid("n"),
            user_id=user_id,
            type=type,
            title=title,
            body=body,
            read_at=None,
            created_at=now_iso(),
        )
    )


# ---------------------------------------------------------------------------
# Enrolment derivation (registration model: program + level)
# ---------------------------------------------------------------------------
def student_course_ids(db: Session, student_id: str) -> List[str]:
    rows = db.scalars(
        select(models.Enrolment).where(
            models.Enrolment.student_id == student_id,
            models.Enrolment.status == "active",
        )
    ).all()
    return [e.course_id for e in rows]


def enrol_student(db: Session, student: models.User) -> None:
    """Re-derive a student's enrolments from their program + level."""
    if student.role != "student":
        return
    for e in db.scalars(
        select(models.Enrolment).where(models.Enrolment.student_id == student.user_id)
    ).all():
        db.delete(e)
    courses = db.scalars(
        select(models.Course).where(
            models.Course.program_id == student.program_id,
            models.Course.level == student.level,
        )
    ).all()
    for c in courses:
        db.add(
            models.Enrolment(
                enrolment_id=uid("e"),
                student_id=student.user_id,
                course_id=c.course_id,
                status="active",
            )
        )


def enrol_students_for_course(db: Session, course: models.Course) -> None:
    """Auto-enrol every student matching a new course's program + level."""
    students = db.scalars(
        select(models.User).where(
            models.User.role == "student",
            models.User.program_id == course.program_id,
            models.User.level == course.level,
        )
    ).all()
    for s in students:
        exists = db.scalar(
            select(models.Enrolment).where(
                models.Enrolment.student_id == s.user_id,
                models.Enrolment.course_id == course.course_id,
            )
        )
        if not exists:
            db.add(
                models.Enrolment(
                    enrolment_id=uid("e"),
                    student_id=s.user_id,
                    course_id=course.course_id,
                    status="active",
                )
            )


# ---------------------------------------------------------------------------
# Serialisers / enrichers — output matches the frontend TypeScript interfaces.
# ---------------------------------------------------------------------------
def enrich_user(db: Session, u: models.User) -> Dict[str, Any]:
    prog = db.get(models.Program, u.program_id) if u.program_id else None
    dept = db.get(models.Department, u.department_id) if u.department_id else None
    out: Dict[str, Any] = {
        "user_id": u.user_id,
        "full_name": u.full_name,
        "email": u.email,
        "role": u.role,
        "created_at": u.created_at,
        "active": bool(u.active),
    }
    if u.index_number is not None:
        out["index_number"] = u.index_number
    out["department"] = u.department or (dept.name if dept else None)
    if u.department_id is not None:
        out["department_id"] = u.department_id
    if u.is_hod is not None:
        out["is_hod"] = bool(u.is_hod)
    if u.program_id is not None:
        out["program_id"] = u.program_id
    out["program_name"] = (prog.name if prog else None) or u.program_name
    if u.level is not None:
        out["level"] = u.level
    if u.admission_year is not None:
        out["admission_year"] = u.admission_year
    if u.avatar_color is not None:
        out["avatar_color"] = u.avatar_color
    return out


def enrich_department(db: Session, d: models.Department) -> Dict[str, Any]:
    programs = db.scalars(
        select(models.Program).where(models.Program.department_id == d.department_id)
    ).all()
    return {
        "department_id": d.department_id,
        "name": d.name,
        "code": d.code,
        "hod_id": d.hod_id,
        "hod_name": d.hod_name,
        "program_count": len(programs),
        "lecturer_count": _count(
            db, models.User, role="lecturer", department_id=d.department_id
        ),
        "student_count": _count(
            db, models.User, role="student", department_id=d.department_id
        ),
        "course_count": _count(db, models.Course, department_id=d.department_id),
    }


def enrich_program(db: Session, p: models.Program) -> Dict[str, Any]:
    dept = db.get(models.Department, p.department_id)
    return {
        "program_id": p.program_id,
        "name": p.name,
        "code": p.code,
        "department_id": p.department_id,
        "department_name": dept.name if dept else None,
        "degree": p.degree,
        "duration_years": p.duration_years,
        "student_count": _count(
            db, models.User, role="student", program_id=p.program_id
        ),
        "course_count": _count(db, models.Course, program_id=p.program_id),
    }


def enrich_course(db: Session, c: models.Course) -> Dict[str, Any]:
    lect = db.get(models.User, c.lecturer_id) if c.lecturer_id else None
    dept = db.get(models.Department, c.department_id) if c.department_id else None
    enrolled = db.scalars(
        select(models.Enrolment).where(
            models.Enrolment.course_id == c.course_id,
            models.Enrolment.status == "active",
        )
    ).all()
    period = active_period(db)
    return {
        "course_id": c.course_id,
        "course_code": c.course_code,
        "title": c.title,
        "lecturer_id": c.lecturer_id,
        "lecturer_name": lect.full_name if lect else None,
        "department_id": c.department_id,
        "department_name": dept.name if dept else None,
        "program_id": c.program_id,
        "program_name": c.program_name,
        "level": c.level,
        "semester_no": c.semester_no,
        "academic_year": c.academic_year,
        "semester": c.semester,
        "credits": c.credits,
        "description": c.description,
        "enrolled_count": len(enrolled),
        "is_current": c.academic_year == period["academic_year"]
        and c.semester_no == period["semester"],
    }


def session_dict(db: Session, s: models.AttendanceSession) -> Dict[str, Any]:
    present = db.scalars(
        select(models.AttendanceRecord).where(
            models.AttendanceRecord.session_id == s.session_id,
            models.AttendanceRecord.status == "present",
        )
    ).all()
    return {
        "session_id": s.session_id,
        "course_id": s.course_id,
        "course_code": s.course_code,
        "lecturer_id": s.lecturer_id,
        "start_time": s.start_time,
        "end_time": s.end_time,
        "geofence": s.geofence,
        "totp_seed": s.totp_seed,
        "rotate_seconds": s.rotate_seconds,
        "status": s.status,
        "present_count": len(present),
    }


def record_dict(r: models.AttendanceRecord) -> Dict[str, Any]:
    out = {
        "record_id": r.record_id,
        "session_id": r.session_id,
        "student_id": r.student_id,
        "student_name": r.student_name,
        "status": r.status,
        "device_id": r.device_id,
        "latitude": r.latitude,
        "longitude": r.longitude,
        "marked_at": r.marked_at,
    }
    if r.reject_reason is not None:
        out["reject_reason"] = r.reject_reason
    return out


def material_dict(m: models.CourseMaterial) -> Dict[str, Any]:
    return {
        "material_id": m.material_id,
        "course_id": m.course_id,
        "course_code": m.course_code,
        "title": m.title,
        "type": m.type,
        "file_key": m.file_key,
        "size_kb": m.size_kb,
        "release_at": m.release_at,
        "expires_at": m.expires_at,
        "uploaded_by": m.uploaded_by,
        "created_at": m.created_at,
        "access_count": m.access_count,
    }


def assignment_dict(db: Session, a: models.Assignment) -> Dict[str, Any]:
    count = len(
        db.scalars(
            select(models.Submission).where(
                models.Submission.assignment_id == a.assignment_id
            )
        ).all()
    )
    return {
        "assignment_id": a.assignment_id,
        "course_id": a.course_id,
        "course_code": a.course_code,
        "title": a.title,
        "instructions": a.instructions,
        "deadline": a.deadline,
        "max_score": a.max_score,
        "created_at": a.created_at,
        "submission_count": count,
    }


def submission_dict(s: models.Submission) -> Dict[str, Any]:
    return {
        "submission_id": s.submission_id,
        "assignment_id": s.assignment_id,
        "student_id": s.student_id,
        "student_name": s.student_name,
        "file_key": s.file_key,
        "file_name": s.file_name,
        "score": s.score,
        "feedback": s.feedback,
        "submitted_at": s.submitted_at,
        "graded_at": s.graded_at,
        "late": bool(s.late),
    }


def exam_dict(e: models.Exam, *, strip_answers: bool = False) -> Dict[str, Any]:
    questions = []
    for q in e.questions or []:
        q = dict(q)
        if strip_answers:
            q["correct_answer"] = -1
        questions.append(q)
    return {
        "exam_id": e.exam_id,
        "course_id": e.course_id,
        "course_code": e.course_code,
        "title": e.title,
        "duration_minutes": e.duration_minutes,
        "start_time": e.start_time,
        "end_time": e.end_time,
        "shuffle": bool(e.shuffle),
        "questions": questions,
        "status": e.status,
    }


def attempt_dict(a: models.ExamAttempt) -> Dict[str, Any]:
    return {
        "attempt_id": a.attempt_id,
        "exam_id": a.exam_id,
        "student_id": a.student_id,
        "student_name": a.student_name,
        "started_at": a.started_at,
        "submitted_at": a.submitted_at,
        "score": a.score,
        "answers": a.answers or {},
        "question_order": a.question_order or [],
        "status": a.status,
        "last_saved_at": a.last_saved_at,
    }


def notification_dict(n: models.Notification) -> Dict[str, Any]:
    return {
        "notification_id": n.notification_id,
        "user_id": n.user_id,
        "type": n.type,
        "title": n.title,
        "body": n.body,
        "read_at": n.read_at,
        "created_at": n.created_at,
    }


def audit_dict(a: models.AuditLog) -> Dict[str, Any]:
    return {
        "log_id": a.log_id,
        "actor_id": a.actor_id,
        "actor_name": a.actor_name,
        "action": a.action,
        "target": a.target,
        "ip_address": a.ip_address,
        "timestamp": a.timestamp,
    }


# ---------------------------------------------------------------------------
# Small internal helper
# ---------------------------------------------------------------------------
def _count(db: Session, model, **filters) -> int:
    stmt = select(model)
    for key, value in filters.items():
        stmt = stmt.where(getattr(model, key) == value)
    return len(db.scalars(stmt).all())
