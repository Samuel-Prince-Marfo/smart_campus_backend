"""Security and shared low-level helpers.

Contains:
  * Password hashing (PBKDF2-HMAC-SHA256, standard library only).
  * JWT access/refresh token creation and decoding.
  * The rotating-QR TOTP derivation, ported byte-for-byte from the frontend's
    `src/lib/totp.ts` so client-generated tokens validate here unchanged.
  * Haversine distance for the attendance geofence check.
  * uid() and ISO timestamp helpers matching the frontend conventions.
"""
from __future__ import annotations

import hashlib
import hmac
import math
import os
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt

from .config import settings

# ---------------------------------------------------------------------------
# Time helpers (ISO 8601, UTC, "...Z" suffix to mirror JS Date.toISOString()).
# ---------------------------------------------------------------------------
def now_dt() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def now_iso() -> str:
    return to_iso(now_dt())


def iso_in_hours(h: float) -> str:
    return to_iso(now_dt() + timedelta(hours=h))


def iso_in_days(d: float) -> str:
    return to_iso(now_dt() + timedelta(days=d))


def parse_iso(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO timestamp (tolerating a trailing 'Z') to an aware datetime."""
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def epoch_ms(value: Optional[str]) -> Optional[float]:
    dt = parse_iso(value)
    return dt.timestamp() * 1000 if dt else None


# ---------------------------------------------------------------------------
# Unique id generator — mirrors `uid(prefix)` in src/lib/utils.ts in shape.
# ---------------------------------------------------------------------------
_ALPHABET = string.ascii_lowercase + string.digits


def uid(prefix: str = "id") -> str:
    rand = "".join(secrets.choice(_ALPHABET) for _ in range(8))
    tail = format(int(now_dt().timestamp() * 1000), "x")[-4:]
    return f"{prefix}_{rand}{tail}"


# ---------------------------------------------------------------------------
# Password hashing — PBKDF2-HMAC-SHA256 with a per-password random salt.
# Format stored in the DB:  pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>
# ---------------------------------------------------------------------------
_PBKDF2_ITERATIONS = 240_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: Optional[str]) -> bool:
    if not stored:
        return False
    try:
        algorithm, iterations_s, salt_hex, hash_hex = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_s)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, AttributeError):
        return False
    candidate = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations
    )
    return hmac.compare_digest(candidate, expected)


# ---------------------------------------------------------------------------
# JWT access / refresh tokens.
# ---------------------------------------------------------------------------
def _create_token(subject: str, token_type: str, expires_minutes: int) -> str:
    now = now_dt()
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expires_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_access_token(subject: str) -> str:
    return _create_token(subject, "access", settings.access_token_expire_minutes)


def create_refresh_token(subject: str) -> str:
    return _create_token(subject, "refresh", settings.refresh_token_expire_minutes)


def decode_token(token: str) -> Optional[dict[str, Any]]:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except jwt.PyJWTError:
        return None


# ---------------------------------------------------------------------------
# Rotating QR / TOTP derivation.
#
# Ported exactly from src/lib/totp.ts. It emulates JavaScript's 32-bit integer
# semantics (ToInt32 + Math.imul) so a token generated in the browser from a
# session seed validates here without any change to the frontend.
# ---------------------------------------------------------------------------
def _to_int32(n: int) -> int:
    n &= 0xFFFFFFFF
    return n - 0x100000000 if n >= 0x80000000 else n


def _imul(a: int, b: int) -> int:
    return _to_int32(((a & 0xFFFFFFFF) * (b & 0xFFFFFFFF)) & 0xFFFFFFFF)


def current_counter(rotate_seconds: int) -> int:
    return int(now_dt().timestamp() // rotate_seconds)


def derive_token(seed: str, counter: int) -> str:
    text = f"{seed}:{counter}"
    h = 2166136261
    for ch in text:
        h = _to_int32(_to_int32(h) ^ ord(ch))
        h = _imul(h, 16777619)
    return str(abs(h) % 1_000_000).zfill(6)


def generate_token(seed: str, rotate_seconds: int) -> str:
    return derive_token(seed, current_counter(rotate_seconds))


def validate_token(seed: str, rotate_seconds: int, token: str) -> bool:
    """Accept the current window's token or the previous one (clock-drift grace)."""
    c = current_counter(rotate_seconds)
    token = str(token)
    return token == derive_token(seed, c) or token == derive_token(seed, c - 1)


# ---------------------------------------------------------------------------
# Haversine distance in metres — mirrors distanceMeters() in src/lib/utils.ts.
# ---------------------------------------------------------------------------
def distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000.0
    to_rad = lambda x: x * math.pi / 180.0  # noqa: E731
    d_lat = to_rad(lat2 - lat1)
    d_lon = to_rad(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(to_rad(lat1)) * math.cos(to_rad(lat2)) * math.sin(d_lon / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
