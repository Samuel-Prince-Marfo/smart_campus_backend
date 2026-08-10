"""Notification endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import enrich, models, security
from ..database import get_db
from ..deps import get_current_user

router = APIRouter(tags=["notifications"])


@router.get("/notifications")
def list_notifications(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    rows = db.scalars(
        select(models.Notification).where(models.Notification.user_id == user.user_id)
    ).all()
    out = [enrich.notification_dict(n) for n in rows]
    out.sort(key=lambda n: security.parse_iso(n["created_at"]) or 0, reverse=True)
    return out


@router.post("/notifications/{notification_id}/read")
def read_notification(
    notification_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    n = db.get(models.Notification, notification_id)
    if n:
        n.read_at = security.now_iso()
        db.commit()
        return enrich.notification_dict(n)
    return None


@router.post("/notifications/read-all")
def read_all(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    rows = db.scalars(
        select(models.Notification).where(
            models.Notification.user_id == user.user_id
        )
    ).all()
    for n in rows:
        if not n.read_at:
            n.read_at = security.now_iso()
    db.commit()
    return {"ok": True}
