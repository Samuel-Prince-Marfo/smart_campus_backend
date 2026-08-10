"""Course material endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import enrich, models, security
from ..database import get_db
from ..deps import get_current_user
from ..schemas import MaterialCreate

router = APIRouter(tags=["materials"])


@router.get("/materials")
def list_materials(
    course_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    rows = db.scalars(select(models.CourseMaterial)).all()

    if course_id:
        rows = [m for m in rows if m.course_id == course_id]
    elif user.role == "student":
        ids = set(enrich.student_course_ids(db, user.user_id))
        rows = [m for m in rows if m.course_id in ids]
    elif user.role == "lecturer":
        my_courses = {
            c.course_id
            for c in db.scalars(
                select(models.Course).where(models.Course.lecturer_id == user.user_id)
            ).all()
        }
        rows = [m for m in rows if m.course_id in my_courses]

    # Students only see released, non-expired materials.
    if user.role == "student":
        now = security.epoch_ms(security.now_iso())
        kept = []
        for m in rows:
            rel = security.epoch_ms(m.release_at)
            if rel is not None and rel > now:
                continue
            exp = security.epoch_ms(m.expires_at) if m.expires_at else None
            if exp is not None and exp < now:
                continue
            kept.append(m)
        rows = kept

    out = [enrich.material_dict(m) for m in rows]
    out.sort(key=lambda m: security.parse_iso(m["created_at"]) or 0, reverse=True)
    return out


@router.post("/materials")
def create_material(
    body: MaterialCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    if user.role == "student":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not permitted")

    course = db.get(models.Course, body.course_id)
    m = models.CourseMaterial(
        material_id=security.uid("m"),
        course_id=body.course_id,
        course_code=course.course_code if course else None,
        title=body.title,
        type=body.type,
        file_key=f"files/{security.uid('f')}",
        size_kb=int(body.size_kb or 0),
        release_at=body.release_at or security.now_iso(),
        expires_at=body.expires_at or None,
        uploaded_by=user.user_id,
        created_at=security.now_iso(),
        access_count=0,
    )
    db.add(m)
    enrich.audit(db, user, "material.upload", m.title)
    db.commit()
    return enrich.material_dict(m)


@router.delete("/materials/{material_id}")
def delete_material(
    material_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    m = db.get(models.CourseMaterial, material_id)
    if m:
        db.delete(m)
    enrich.audit(db, user, "material.delete", material_id)
    db.commit()
    return {"ok": True}


@router.post("/materials/{material_id}/access")
def access_material(material_id: str, db: Session = Depends(get_db)):
    m = db.get(models.CourseMaterial, material_id)
    if not m:
        return None
    m.access_count = (m.access_count or 0) + 1
    db.commit()
    return enrich.material_dict(m)
