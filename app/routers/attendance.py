"""Attendance endpoints: rotating-QR sessions, geofenced marking, history."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import enrich, models, security
from ..database import get_db
from ..deps import get_current_user
from ..schemas import AttendanceMark, AttendanceSessionCreate

router = APIRouter(tags=["attendance"])


@router.get("/attendance/sessions")
def list_sessions(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    rows = db.scalars(select(models.AttendanceSession)).all()
    if user.role == "lecturer":
        rows = [s for s in rows if s.lecturer_id == user.user_id]
    elif user.role == "student":
        ids = set(enrich.student_course_ids(db, user.user_id))
        rows = [s for s in rows if s.course_id in ids]
    out = [enrich.session_dict(db, s) for s in rows]
    out.sort(key=lambda s: security.parse_iso(s["start_time"]) or 0, reverse=True)
    return out


@router.post("/attendance/sessions")
def start_session(
    body: AttendanceSessionCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    if user.role not in ("lecturer", "admin"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only lecturers can start sessions"
        )
    course = db.get(models.Course, body.course_id)
    settings = enrich.get_settings(db)
    s = models.AttendanceSession(
        session_id=security.uid("as"),
        course_id=body.course_id,
        course_code=course.course_code if course else None,
        lecturer_id=user.user_id,
        start_time=security.now_iso(),
        end_time=security.iso_in_hours((body.duration_minutes or 90) / 60.0),
        geofence=body.geofence.model_dump(),
        totp_seed=f"seed-{security.uid('s')}",
        rotate_seconds=int(settings.get("rotate_seconds", 15)) or 15,
        status="open",
    )
    db.add(s)
    enrich.audit(db, user, "attendance.session.start", course.course_code if course else body.course_id)

    enrolments = db.scalars(
        select(models.Enrolment).where(
            models.Enrolment.course_id == body.course_id,
            models.Enrolment.status == "active",
        )
    ).all()
    for e in enrolments:
        enrich.notify(
            db, e.student_id,
            type="attendance",
            title=f"Attendance open: {course.course_code if course else ''}",
            body=f"Mark your attendance in {body.geofence.label}.",
        )
    db.commit()
    return enrich.session_dict(db, s)


@router.post("/attendance/sessions/{session_id}/close")
def close_session(
    session_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    s = db.get(models.AttendanceSession, session_id)
    if not s:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    s.status = "closed"
    s.end_time = security.now_iso()
    enrich.audit(db, user, "attendance.session.close", s.course_code or s.session_id)
    db.commit()
    return enrich.session_dict(db, s)


@router.get("/attendance/sessions/{session_id}/records")
def session_records(
    session_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    rows = db.scalars(
        select(models.AttendanceRecord).where(
            models.AttendanceRecord.session_id == session_id
        )
    ).all()
    return [enrich.record_dict(r) for r in rows]


@router.post("/attendance/sessions/{session_id}/mark")
def mark_attendance(
    session_id: str,
    body: AttendanceMark,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    s = db.get(models.AttendanceSession, session_id)
    if not s:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    if s.status != "open":
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This attendance session is closed"
        )

    already = db.scalar(
        select(models.AttendanceRecord).where(
            models.AttendanceRecord.session_id == s.session_id,
            models.AttendanceRecord.student_id == user.user_id,
            models.AttendanceRecord.status == "present",
        )
    )
    if already:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "You have already marked attendance for this session",
        )

    # 1) Rotating-QR / TOTP check.
    if not security.validate_token(s.totp_seed, s.rotate_seconds, body.token):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "The QR code has expired. Please rescan the live code.",
        )

    geo = s.geofence or {}
    # 2) Geofence check.
    dist = security.distance_meters(
        geo.get("latitude"), geo.get("longitude"), body.latitude, body.longitude
    )
    if dist > geo.get("radius_m", 0):
        rejected = models.AttendanceRecord(
            record_id=security.uid("ar"),
            session_id=s.session_id,
            student_id=user.user_id,
            student_name=user.full_name,
            status="rejected",
            device_id=body.device_id,
            latitude=body.latitude,
            longitude=body.longitude,
            marked_at=security.now_iso(),
            reject_reason=f"Outside geofence ({round(dist)}m away)",
        )
        db.add(rejected)
        db.commit()
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"You appear to be {round(dist)}m from {geo.get('label')}. "
            "Move closer and try again.",
        )

    # 3) Device binding — reject if bound to a different device previously.
    prior = db.scalar(
        select(models.AttendanceRecord).where(
            models.AttendanceRecord.student_id == user.user_id,
            models.AttendanceRecord.status == "present",
            models.AttendanceRecord.device_id.is_not(None),
        )
    )
    if prior and prior.device_id != body.device_id:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "This account is bound to a different device. "
            "Ask an administrator to reassign it.",
        )

    record = models.AttendanceRecord(
        record_id=security.uid("ar"),
        session_id=s.session_id,
        student_id=user.user_id,
        student_name=user.full_name,
        status="present",
        device_id=body.device_id,
        latitude=body.latitude,
        longitude=body.longitude,
        marked_at=security.now_iso(),
    )
    db.add(record)
    enrich.audit(db, user, "attendance.mark", s.session_id)
    db.commit()
    return enrich.record_dict(record)


@router.get("/attendance/my")
def my_attendance(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    ids = set(enrich.student_course_ids(db, user.user_id))
    sessions = [
        s
        for s in db.scalars(select(models.AttendanceSession)).all()
        if s.course_id in ids
    ]
    result = []
    for s in sessions:
        rec = db.scalar(
            select(models.AttendanceRecord).where(
                models.AttendanceRecord.session_id == s.session_id,
                models.AttendanceRecord.student_id == user.user_id,
            )
        )
        status_value = (
            rec.status if rec else ("pending" if s.status == "open" else "absent")
        )
        result.append(
            {
                "session": enrich.session_dict(db, s),
                "status": status_value,
                "marked_at": rec.marked_at if rec else None,
            }
        )
    return result
