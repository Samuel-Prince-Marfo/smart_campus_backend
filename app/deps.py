"""Authentication dependencies and role guards."""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from . import models, security
from .database import get_db

# auto_error=False so we can raise a 401 with a frontend-friendly `detail`.
_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
) -> models.User:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    payload = security.decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    user = db.get(models.User, payload.get("sub"))
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    return user


def require_admin(user: models.User = Depends(get_current_user)) -> models.User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admins only")
    return user


def require_staff(user: models.User = Depends(get_current_user)) -> models.User:
    """Lecturers or admins (i.e. not students)."""
    if user.role == "student":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not permitted")
    return user
