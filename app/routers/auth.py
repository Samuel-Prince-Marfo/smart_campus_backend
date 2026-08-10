"""Authentication endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import enrich, models, security
from ..database import get_db
from ..deps import get_current_user
from ..schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
)

router = APIRouter(tags=["auth"])


def _auth_response(db: Session, user: models.User) -> dict:
    return {
        "access_token": security.create_access_token(user.user_id),
        "refresh_token": security.create_refresh_token(user.user_id),
        "user": enrich.enrich_user(db, user),
    }


@router.post("/auth/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(
        select(models.User).where(func.lower(models.User.email) == body.email.lower())
    )
    if not user or not security.verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if not user.active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account is deactivated")
    enrich.audit(db, user, "auth.login", user.email)
    db.commit()
    return _auth_response(db, user)


@router.post("/auth/register")
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    settings = enrich.get_settings(db)
    if not settings.get("allow_self_register", True):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Self-registration is disabled")
    exists = db.scalar(
        select(models.User).where(func.lower(models.User.email) == body.email.lower())
    )
    if exists:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "An account with this email already exists"
        )

    role = "lecturer" if body.role == "lecturer" else "student"
    prog = db.get(models.Program, body.program_id) if body.program_id else None
    dept_id = prog.department_id if role == "student" and prog else body.department_id
    dept = db.get(models.Department, dept_id) if dept_id else None

    user = models.User(
        user_id=security.uid("u"),
        full_name=body.full_name,
        email=body.email,
        role=role,
        password_hash=security.hash_password(body.password),
        index_number=body.index_number,
        department_id=dept_id,
        department=dept.name if dept else None,
        program_id=body.program_id if role == "student" else None,
        program_name=prog.name if (role == "student" and prog) else None,
        level=int(body.level) if (role == "student" and body.level) else None,
        admission_year=(body.admission_year or str(settings.get("active_year")))
        if role == "student"
        else None,
        avatar_color="#cf8a1d",
        created_at=security.now_iso(),
        active=True,
    )
    db.add(user)
    db.flush()
    if role == "student":
        enrich.enrol_student(db, user)
    enrich.audit(db, user, "user.register", user.email)
    db.commit()
    return _auth_response(db, user)


@router.post("/auth/forgot-password")
def forgot_password(body: ForgotPasswordRequest):
    # Always returns success to avoid account enumeration, like a real backend.
    return {"ok": True, "message": f"If {body.email} exists, a reset link has been sent."}


@router.get("/auth/me")
def me(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return enrich.enrich_user(db, user)


@router.post("/auth/refresh")
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    payload = security.decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    user = db.get(models.User, payload.get("sub"))
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    return _auth_response(db, user)
