"""Application configuration.

All settings have safe defaults so the server runs with no .env file. Values can
be overridden via environment variables or a `.env` file (see .env.example).
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Smart Campus API"
    app_version: str = "1.0.0"

    # Database — SQLite by default (zero configuration, file-based).
    database_url: str = "sqlite:///./smart_campus.db"

    # JWT signing.
    secret_key: str = "change-me-in-production-please-use-a-long-random-string"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 720       # 12 hours
    refresh_token_expire_minutes: int = 20160     # 14 days

    # CORS — list of allowed browser origins, or ["*"] for any.
    cors_origins: List[str] = ["*"]

    # Seed demo data on first startup if the database is empty.
    seed_on_startup: bool = True

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value):
        # Accept a comma-separated string from the environment.
        if isinstance(value, str):
            value = value.strip()
            if value == "*":
                return ["*"]
            return [v.strip() for v in value.split(",") if v.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
