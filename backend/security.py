"""
security.py — Passwords, access tokens and opaque tokens.

  Passwords      argon2id (argon2-cffi defaults, OWASP-recommended); hashes are
                 upgraded transparently on login if the parameters change.
  Access token   short-lived JWT (HS256, 15 min) in an httpOnly cookie. Holds
                 only the user id; the user row is still loaded per request,
                 so a deactivated user loses access immediately.
  Opaque tokens  refresh, verify-email and reset-password tokens are random
                 32-byte strings; only their SHA-256 hash is stored.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from backend.config import Settings

_hasher = PasswordHasher()

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128  # argon2 handles any length; this caps abuse


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


# A real hash to verify against when the email doesn't exist, so a login for an
# unknown email takes as long as one with a wrong password (no timing oracle).
DUMMY_HASH = _hasher.hash("not-a-real-password")


def password_problem(password: str, email: str = "") -> str | None:
    """Why a new password is unacceptable, or None."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if len(password) > MAX_PASSWORD_LENGTH:
        return f"Password must be at most {MAX_PASSWORD_LENGTH} characters."
    if email and password.strip().lower() == email.strip().lower():
        return "Password must not be your email address."
    if len(set(password)) < 4:
        return "Password is too simple."
    return None


def as_utc(dt: datetime) -> datetime:
    """SQLite returns naive datetimes; treat them as UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ─── Access tokens (JWT) ──────────────────────────────────────────────────────

def create_access_token(user_id: str, settings: Settings) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> str | None:
    """User id from a valid, unexpired access token; None otherwise."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm],
                             options={"require": ["sub", "exp", "type"]})
    except jwt.PyJWTError:
        return None
    return payload["sub"] if payload.get("type") == "access" else None


# ─── Opaque tokens ────────────────────────────────────────────────────────────

def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
