"""Departments, programs and academic-period endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import enrich, models, security
from ..database import get_db
from ..deps import get_current_user, require_admin
from ..schemas import (
    AcademicPeriodUpdate,
    DepartmentCreate,
    DepartmentUpdate,
    ProgramCreate,
)

router = APIRouter(tags=["institution"])


# ----- Departments ----------------------------------------------------------
@router.get("/departments")
def list_departments(db: Session = Depends(get_db)):
    rows = db.scalars(select(models.Department)).all()
    return [enrich.enrich_department(db, d) for d in rows]


@router.get("/departments/{department_id}")
def get_department(department_id: str, db: Session = Depends(get_db)):
    d = db.get(models.Department, department_id)
    if not d:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Department not found")
    return enrich.enrich_department(db, d)


@router.post("/departments")
def create_department(
    body: DepartmentCreate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    d = models.Department(
        department_id=security.uid("d"),
        name=body.name,
        code=body.code,
        hod_id=body.hod_id or None,
    )
    hod = db.get(models.User, body.hod_id) if body.hod_id else None
    d.hod_name = hod.full_name if hod else None
    db.add(d)
    enrich.audit(db, admin, "department.create", d.name)
    db.commit()
    return enrich.enrich_department(db, d)


@router.patch("/departments/{department_id}")
def update_department(
    department_id: str,
    body: DepartmentUpdate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    d = db.get(models.Department, department_id)
    if not d:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Department not found")
    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(d, key, value)
    if data.get("hod_id"):
        hod = db.get(models.User, data["hod_id"])
        d.hod_name = hod.full_name if hod else None
    enrich.audit(db, admin, "department.update", d.name)
    db.commit()
    return enrich.enrich_department(db, d)


# ----- Programs --------------------------------------------------------------
@router.get("/programs")
def list_programs(
    department_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    stmt = select(models.Program)
    if department_id:
        stmt = stmt.where(models.Program.department_id == department_id)
    rows = db.scalars(stmt).all()
    return [enrich.enrich_program(db, p) for p in rows]


@router.post("/programs")
def create_program(
    body: ProgramCreate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    p = models.Program(
        program_id=security.uid("p"),
        name=body.name,
        code=body.code,
        department_id=body.department_id,
        degree=body.degree or "BSc",
        duration_years=int(body.duration_years or 4),
    )
    db.add(p)
    enrich.audit(db, admin, "program.create", p.name)
    db.commit()
    return enrich.enrich_program(db, p)


# ----- Academic period -------------------------------------------------------
@router.get("/academic/period")
def get_period(db: Session = Depends(get_db)):
    return enrich.active_period(db)


@router.patch("/admin/academic-period")
def set_period(
    body: AcademicPeriodUpdate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    row = enrich.get_settings_row(db)
    data = dict(row.data)
    if body.academic_year:
        data["active_year"] = body.academic_year
    if body.semester is not None:
        data["active_semester"] = 2 if int(body.semester) == 2 else 1
    row.data = data
    enrich.audit(
        db, admin, "academic.period.update",
        f"{data.get('active_year')} Sem {data.get('active_semester')}",
    )
    db.commit()
    return enrich.active_period(db)
