"""Course endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import enrich, models, security
from ..database import get_db
from ..deps import get_current_user
from ..schemas import CourseCreate

router = APIRouter(tags=["courses"])


@router.get("/courses")
def list_courses(
    department_id: Optional[str] = Query(None),
    program_id: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    semester: Optional[str] = Query(None),
    year: Optional[str] = Query(None),
    current: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    rows = db.scalars(select(models.Course)).all()

    if user.role == "student":
        ids = set(enrich.student_course_ids(db, user.user_id))
        rows = [c for c in rows if c.course_id in ids]
    elif user.role == "lecturer":
        rows = [
            c
            for c in rows
            if c.lecturer_id == user.user_id
            or (user.is_hod and c.department_id == user.department_id)
        ]

    if department_id:
        rows = [c for c in rows if c.department_id == department_id]
    if program_id:
        rows = [c for c in rows if c.program_id == program_id]
    if level:
        rows = [c for c in rows if str(c.level) == level]
    if semester:
        rows = [c for c in rows if str(c.semester_no) == semester]
    if year:
        rows = [c for c in rows if c.academic_year == year]
    if current == "true":
        period = enrich.active_period(db)
        rows = [
            c
            for c in rows
            if c.academic_year == period["academic_year"]
            and c.semester_no == period["semester"]
        ]

    return [enrich.enrich_course(db, c) for c in rows]


@router.get("/courses/{course_id}")
def get_course(course_id: str, db: Session = Depends(get_db)):
    c = db.get(models.Course, course_id)
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    return enrich.enrich_course(db, c)


@router.post("/courses")
def create_course(
    body: CourseCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    if user.role == "student":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not permitted")

    prog = db.get(models.Program, body.program_id) if body.program_id else None
    period = enrich.active_period(db)
    year = body.academic_year or period["academic_year"]
    sem_no = 2 if int(body.semester_no or 1) == 2 else 1

    if user.role == "lecturer" and prog and prog.department_id != user.department_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "You can only create courses within your department",
        )

    c = models.Course(
        course_id=security.uid("c"),
        course_code=body.course_code,
        title=body.title,
        lecturer_id=body.lecturer_id or user.user_id,
        department_id=(prog.department_id if prog else None) or user.department_id,
        program_id=body.program_id,
        program_name=prog.name if prog else None,
        level=int(body.level) if body.level else None,
        semester_no=sem_no,
        academic_year=year,
        semester=f"{year} · Sem {sem_no}",
        credits=int(body.credits or 3),
        description=body.description,
    )
    db.add(c)
    db.flush()
    enrich.enrol_students_for_course(db, c)
    enrich.audit(db, user, "course.create", c.course_code)
    db.commit()
    return enrich.enrich_course(db, c)


@router.get("/courses/{course_id}/students")
def course_students(
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
    students = db.scalars(
        select(models.User).where(models.User.user_id.in_(ids))
    ).all()
    return [enrich.enrich_user(db, s) for s in students]
