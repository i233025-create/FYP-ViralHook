"""
config.py — Settings for the product backend, read from environment variables.

  DATABASE_URL          sqlite:///<ROOT>/data/viralhook.db by default;
                        postgresql+psycopg://user:pass@host/db in production
  JWT_SECRET            signing key for access tokens. Required when
                        APP_ENV=production; in development a random key is
                        generated once and kept in data/.jwt_secret
  APP_ENV               development (default) | production
  COOKIE_SECURE         1 to send cookies only over HTTPS (default: on in production)
  ALLOWED_ORIGINS       comma-separated browser origins allowed to call the API
  FRONTEND_URL          base URL used in email links (verify / reset)
  ACCESS_TOKEN_MINUTES  default 15
  REFRESH_TOKEN_DAYS    default 30
  MAILER                console (default) | smtp (not implemented yet)
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).parent.parent.resolve()
DATA_DIR = Path(os.getenv("VIRALHOOK_DATA_DIR", ROOT / "data"))


def _flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in ("1", "true", "yes", "on")


def _dev_jwt_secret() -> str:
    """Stable random secret for development, so logins survive a server restart."""
    path = DATA_DIR / ".jwt_secret"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    secret = secrets.token_urlsafe(48)
    path.write_text(secret, encoding="utf-8")
    return secret


@dataclass(frozen=True)
class Settings:
    env: str
    database_url: str
    jwt_secret: str
    cookie_secure: bool
    allowed_origins: tuple[str, ...]
    frontend_url: str
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    verify_token_hours: int = 24
    reset_token_minutes: int = 60
    mailer: str = "console"
    # Login throttling: failures allowed per window before 429
    max_failures_per_email: int = 5
    max_failures_per_ip: int = 20
    failure_window_minutes: int = 15
    jwt_algorithm: str = field(default="HS256")

    @property
    def production(self) -> bool:
        return self.env == "production"


@lru_cache
def get_settings() -> Settings:
    env = os.getenv("APP_ENV", "development").strip().lower()
    secret = os.getenv("JWT_SECRET", "").strip()
    if not secret:
        if env == "production":
            raise RuntimeError("JWT_SECRET must be set when APP_ENV=production")
        secret = _dev_jwt_secret()
    origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return Settings(
        env=env,
        database_url=os.getenv("DATABASE_URL", f"sqlite:///{(DATA_DIR / 'viralhook.db').as_posix()}"),
        jwt_secret=secret,
        cookie_secure=_flag("COOKIE_SECURE", env == "production"),
        allowed_origins=tuple(o.strip().rstrip("/") for o in origins.split(",") if o.strip()),
        frontend_url=os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/"),
        access_token_minutes=int(os.getenv("ACCESS_TOKEN_MINUTES", "15")),
        refresh_token_days=int(os.getenv("REFRESH_TOKEN_DAYS", "30")),
        mailer=os.getenv("MAILER", "console").strip().lower(),
    )
