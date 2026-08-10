"""Analytics endpoints: dashboards, per-course risk, system overview."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import enrich, models
from ..database import get_db
from ..deps import get_current_user, require_admin

router = APIRouter(tags=["analytics"])

_TREND_LABELS = ["Wk 1", "Wk 2", "Wk 3", "Wk 4", "Wk 5", "Wk 6"]


def _trend(user_id: str) -> list[dict]:
    out = []
    for i, label in enumerate(_TREND_LABELS):
        attendance = 70 + ((i * 7 + (len(user_id) % 5) * 3) % 28)
        performance = 60 + ((i * 9 + 11) % 35)
        out.append({"label": label, "attendance": attendance, "performance": performance})
    return out


def _unread(db: Session, user_id: str) -> int:
    rows = db.scalars(
        select(models.Notification).where(models.Notification.user_id == user_id)
    ).all()
    return len([n for n in rows if not n.read_at])


@router.get("/analytics/dashboard")
def dashboard(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    trend = _trend(user.user_id)

    if user.role == "student":
        ids = set(enrich.student_course_ids(db, user.user_id))
        sessions = [
            s
            for s in db.scalars(select(models.AttendanceSession)).all()
            if s.course_id in ids and s.status == "closed"
        ]
        records = db.scalars(
            select(models.AttendanceRecord).where(
                models.AttendanceRecord.student_id == user.user_id,
                models.AttendanceRecord.status == "present",
            )
        ).all()
        present_sessions = {r.session_id for r in records}
        present = len([s for s in sessions if s.session_id in present_sessions])
        attendance_rate = round((present / len(sessions)) * 100) if sessions else 92

        assignments = [
            a
            for a in db.scalars(select(models.Assignment)).all()
            if a.course_id in ids
        ]
        my_subs = {
            s.assignment_id
            for s in db.scalars(
                select(models.Submission).where(
                    models.Submission.student_id == user.user_id
                )
            ).all()
        }
        pending = len([a for a in assignments if a.assignment_id not in my_subs])
        exams = [
            e
            for e in db.scalars(select(models.Exam)).all()
            if e.course_id in ids and e.status != "closed"
        ]
        return {
            "attendance_rate": attendance_rate,
            "pending_assignments": pending,
            "upcoming_exams": len(exams),
            "unread_notifications": _unread(db, user.user_id),
            "courses": len(ids),
            "trend": trend,
        }

    if user.role == "lecturer":
        my_courses = {
            c.course_id
            for c in db.scalars(
                select(models.Course).where(models.Course.lecturer_id == user.user_id)
            ).all()
        }
        my_assignments = {
            a.assignment_id: a.course_id
            for a in db.scalars(select(models.Assignment)).all()
        }
        pending = len(
            [
                s
                for s in db.scalars(select(models.Submission)).all()
                if my_assignments.get(s.assignment_id) in my_courses and s.score is None
            ]
        )
        exams = [
            e
            for e in db.scalars(select(models.Exam)).all()
            if e.course_id in my_courses and e.status != "closed"
        ]
        return {
            "attendance_rate": 86,
            "pending_assignments": pending,
            "upcoming_exams": len(exams),
            "unread_notifications": _unread(db, user.user_id),
            "courses": len(my_courses),
            "trend": trend,
        }

    # admin
    pending = len(
        [s for s in db.scalars(select(models.Submission)).all() if s.score is None]
    )
    exams = [e for e in db.scalars(select(models.Exam)).all() if e.status != "closed"]
    courses = db.scalars(select(models.Course)).all()
    return {
        "attendance_rate": 84,
        "pending_assignments": pending,
        "upcoming_exams": len(exams),
        "unread_notifications": _unread(db, user.user_id),
        "courses": len(courses),
        "trend": trend,
    }


@router.get("/analytics/course/{course_id}")
def course_analytics(
    course_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    ids = [
        e.student_id
        for e in db.scalars(
            select(models.Enrolment).where(
                models.Enrolment.course_id == course_id,
                models.Enrolment.status == "active",
            )
        ).all()
    ]
    sessions = db.scalars(
        select(models.AttendanceSession).where(
            models.AttendanceSession.course_id == course_id
        )
    ).all()
    assignments = db.scalars(
        select(models.Assignment).where(models.Assignment.course_id == course_id)
    ).all()
    assignment_ids = {a.assignment_id for a in assignments}
    max_by_assignment = {a.assignment_id: (a.max_score or 100) for a in assignments}
    all_records = db.scalars(select(models.AttendanceRecord)).all()
    all_submissions = db.scalars(select(models.Submission)).all()

    risks = []
    for sid in ids:
        u = db.get(models.User, sid)
        if not u:
            continue
        present = 0
        for s in sessions:
            if any(
                r.session_id == s.session_id
                and r.student_id == sid
                and r.status == "present"
                for r in all_records
            ):
                present += 1
        attendance_rate = round((present / len(sessions)) * 100) if sessions else 80

        subs = [
            s
            for s in all_submissions
            if s.assignment_id in assignment_ids and s.student_id == sid
        ]
        graded = [s for s in subs if s.score is not None]
        if graded:
            avg = round(
                sum(
                    (s.score / max_by_assignment.get(s.assignment_id, 100)) * 100
                    for s in graded
                )
                / len(graded)
            )
        else:
            avg = 70
        submission_rate = (
            round((len(subs) / len(assignments)) * 100) if assignments else 100
        )
        composite = attendance_rate * 0.4 + avg * 0.4 + submission_rate * 0.2
        risk = "low" if composite >= 75 else "medium" if composite >= 55 else "high"
        risks.append(
            {
                "student_id": sid,
                "student_name": u.full_name,
                "attendance_rate": attendance_rate,
                "avg_score": avg,
                "submission_rate": submission_rate,
                "risk": risk,
            }
        )

    risks.sort(key=lambda r: r["avg_score"])
    return risks


@router.get("/analytics/overview")
def overview(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_admin),
):
    users = db.scalars(select(models.User)).all()
    departments = db.scalars(select(models.Department)).all()
    programs = db.scalars(select(models.Program)).all()
    courses = db.scalars(select(models.Course)).all()
    sessions = db.scalars(select(models.AttendanceSession)).all()
    submissions = db.scalars(select(models.Submission)).all()
    period = enrich.active_period(db)

    students = [u for u in users if u.role == "student"]
    return {
        "users": len(users),
        "students": len(students),
        "lecturers": len([u for u in users if u.role == "lecturer"]),
        "departments": len(departments),
        "programs": len(programs),
        "courses": len(courses),
        "sessions": len(sessions),
        "submissions": len(submissions),
        "active_period": f"{period['academic_year']} \u00b7 Sem {period['semester']}",
        "by_department": [
            {
                "name": d.code,
                "value": len(
                    [s for s in students if s.department_id == d.department_id]
                ),
            }
            for d in departments
        ],
        "by_program": [
            {
                "name": p.code,
                "value": len([s for s in students if s.program_id == p.program_id]),
            }
            for p in programs
        ],
        "students_by_level": [
            {"name": f"L{lvl}", "value": len([s for s in students if s.level == lvl])}
            for lvl in (100, 200, 300, 400)
        ],
    }
