"""Admin endpoints: user management, audit log, settings, demo reset."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import enrich, models, security
from ..database import get_db
from ..deps import require_admin
from ..schemas import AdminUserCreate, AdminUserUpdate, SettingsUpdate

router = APIRouter(tags=["admin"])

_UPDATABLE_USER_FIELDS = {
    "full_name",
    "email",
    "role",
    "index_number",
    "department_id",
    "is_hod",
    "program_id",
    "level",
    "admission_year",
    "avatar_color",
    "active",
}


@router.get("/admin/users")
def list_users(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_admin),
):
    rows = db.scalars(select(models.User)).all()
    return [enrich.enrich_user(db, u) for u in rows]


@router.post("/admin/users")
def create_user(
    body: AdminUserCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_admin),
):
    existing = db.scalar(
        select(models.User).where(models.User.email == body.email)
    )
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already in use")

    prog = db.get(models.Program, body.program_id) if body.program_id else None
    dept_id = (
        (prog.department_id if prog else None)
        if body.role == "student"
        else body.department_id
    )
    dept = db.get(models.Department, dept_id) if dept_id else None

    u = models.User(
        user_id=security.uid("u"),
        full_name=body.full_name,
        email=body.email,
        role=body.role,
        password_hash=security.hash_password(body.password or "password"),
        index_number=body.index_number,
        department_id=dept_id,
        department=dept.name if dept else None,
        program_id=body.program_id if body.role == "student" else None,
        program_name=(prog.name if prog else None) if body.role == "student" else None,
        level=int(body.level) if (body.role == "student" and body.level) else None,
        admission_year=(
            body.admission_year or enrich.active_period(db)["academic_year"]
        )
        if body.role == "student"
        else None,
        is_hod=bool(body.is_hod) if body.role == "lecturer" else None,
        avatar_color="#4f6678",
        created_at=security.now_iso(),
        active=True,
    )
    db.add(u)
    db.flush()
    if u.role == "student":
        enrich.enrol_student(db, u)
    enrich.audit(db, user, "user.create", u.email)
    db.commit()
    return enrich.enrich_user(db, u)


@router.patch("/admin/users/{user_id}")
def update_user(
    user_id: str,
    body: AdminUserUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_admin),
):
    u = db.get(models.User, user_id)
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        if key in _UPDATABLE_USER_FIELDS:
            setattr(u, key, value)

    if u.role == "student" and ("program_id" in data or "level" in data):
        prog = db.get(models.Program, u.program_id) if u.program_id else None
        u.department_id = prog.department_id if prog else None
        dept = db.get(models.Department, u.department_id) if u.department_id else None
        u.department = dept.name if dept else None
        u.program_name = prog.name if prog else None
        db.flush()
        enrich.enrol_student(db, u)

    enrich.audit(db, user, "user.update", u.email)
    db.commit()
    return enrich.enrich_user(db, u)


@router.get("/admin/audit")
def audit_log(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_admin),
):
    rows = db.scalars(select(models.AuditLog)).all()
    rows = sorted(
        rows, key=lambda a: security.parse_iso(a.timestamp) or 0, reverse=True
    )
    return [enrich.audit_dict(a) for a in rows[:200]]


@router.get("/admin/settings")
def get_settings(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_admin),
):
    return enrich.get_settings(db)


@router.patch("/admin/settings")
def update_settings(
    body: SettingsUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_admin),
):
    row = enrich.get_settings_row(db)
    merged = dict(row.data)
    patch = body.to_dict()
    merged.update(patch)
    row.data = merged
    enrich.audit(db, user, "settings.update", ",".join(patch.keys()))
    db.commit()
    return dict(merged)


@router.post("/admin/reset-demo")
def reset_demo(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_admin),
):
    from ..seed import seed_database

    seed_database(db)
    return {"ok": True}
