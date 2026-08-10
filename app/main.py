"""Smart Campus API — application entry point.

Mounts every feature router under the `/api` prefix (the exact contract the
frontend's mock server defines), configures CORS, and seeds the demo dataset on
first startup. Run with:

    uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .config import settings
from .database import Base, SessionLocal, engine
from .routers import (
    admin,
    analytics,
    assignments,
    attendance,
    auth,
    courses,
    exams,
    institution,
    materials,
    notifications,
)
from .seed import database_is_empty, seed_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables, then seed the demo dataset on first run (empty DB).
    Base.metadata.create_all(bind=engine)
    if settings.seed_on_startup:
        db = SessionLocal()
        try:
            if database_is_empty(db):
                seed_database(db)
        finally:
            db.close()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Backend for the Smart Campus academic management & learning system.",
    lifespan=lifespan,
)

# CORS — Bearer-token auth (no cookies), so credentials are not allowed. Lock the
# origins down in production by setting CORS_ORIGINS to your frontend's URL.
_allow_all = settings.cors_origins == ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=".*" if _allow_all else None,
    allow_credentials=not _allow_all,
    allow_methods=["*"],
    allow_headers=["*"],
)

# All feature routers live under the `/api` prefix.
_ROUTERS = [
    auth.router,
    institution.router,
    courses.router,
    attendance.router,
    materials.router,
    assignments.router,
    exams.router,
    analytics.router,
    notifications.router,
    admin.router,
]
for r in _ROUTERS:
    app.include_router(r, prefix="/api")


@app.get("/", tags=["meta"])
def root():
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "api_base": "/api",
        "status": "ok",
    }


@app.get("/health", tags=["meta"])
def health():
    return {"status": "healthy", "version": __version__}
