"""
auth.py — /auth routes and the current-user dependency.

Sessions use two httpOnly cookies:
  vh_access   JWT, 15 min, sent to every path
  vh_refresh  opaque token, 30 days, sent only to /auth; rotated on every
              refresh. Re-using an already-rotated token (a sign it was
              stolen) revokes all of the user's sessions.

Cookies are SameSite=Lax and httpOnly (JavaScript can't read them), and
`install_origin_guard` rejects state-changing requests from foreign origins,
which together protect against CSRF.

Email verification is "soft": users can use the app right away;
`require_verified` guards the sensitive actions (Instagram, payments).

Routes:
  POST /auth/signup                 {name, email, password}      → 201 {user}
  POST /auth/login                  {email, password}            → {user}
  POST /auth/refresh                (refresh cookie)             → {user}
  POST /auth/logout                                              → 204
  POST /auth/logout-all             (signed in)                  → 204
  GET  /auth/me                     (signed in)                  → {user}
  POST /auth/verify-email           {token}                      → {user}
  POST /auth/resend-verification    (signed in)                  → 202
  POST /auth/forgot-password        {email}                      → 202 (always)
  POST /auth/reset-password         {token, password}            → 204
  POST /auth/change-password        {current_password, new_password} → 204
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from backend import mailer as mail
from backend.config import Settings, get_settings
from backend.db import get_db
from backend.models import EmailToken, LoginAttempt, RefreshSession, User, utcnow
from backend.security import (
    DUMMY_HASH, MAX_PASSWORD_LENGTH, as_utc, create_access_token, decode_access_token,
    hash_password, needs_rehash, new_token, password_problem, token_hash, verify_password,
)

ACCESS_COOKIE = "vh_access"
REFRESH_COOKIE = "vh_refresh"
REFRESH_PATH = "/auth"
# Behind a proxy that serves the API under a prefix (Vite dev server and nginx
# use /api), the browser sees /api/auth/...; the proxy says so in this header.
_PREFIX = re.compile(r"/[A-Za-z0-9_-]{1,32}")
# Two tabs refreshing at the same moment both present the same token; the
# loser is refused without being treated as token theft.
REUSE_GRACE_SECONDS = 30

router = APIRouter(prefix="/auth", tags=["auth"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class UserOut(BaseModel):
    id: str
    email: str
    name: str
    emailVerified: bool
    createdAt: datetime

    @classmethod
    def of(cls, user: User) -> "UserOut":
        return cls(id=user.id, email=user.email, name=user.name,
                   emailVerified=user.email_verified, createdAt=as_utc(user.created_at))


class UserResponse(BaseModel):
    user: UserOut


class SignupIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(max_length=MAX_PASSWORD_LENGTH)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Name is required.")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=MAX_PASSWORD_LENGTH)


class TokenIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)


class EmailIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    password: str = Field(max_length=MAX_PASSWORD_LENGTH)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(max_length=MAX_PASSWORD_LENGTH)
    new_password: str = Field(max_length=MAX_PASSWORD_LENGTH)


# ─── Dependencies ─────────────────────────────────────────────────────────────

def settings_dep() -> Settings:
    return get_settings()


def mailer_dep(settings: Settings = Depends(settings_dep)) -> mail.Mailer:
    return mail.get_mailer(settings)


def get_current_user(request: Request, db: Session = Depends(get_db),
                     settings: Settings = Depends(settings_dep)) -> User:
    """The signed-in user, or 401. Loaded fresh, so deactivation applies at once."""
    token = request.cookies.get(ACCESS_COOKIE)
    user_id = decode_access_token(token, settings) if token else None
    user = db.get(User, user_id) if user_id else None
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in.")
    return user


def require_verified(user: User = Depends(get_current_user)) -> User:
    if not user.email_verified:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Please verify your email address first.")
    return user


def install_origin_guard(app, settings: Settings | None = None) -> None:
    """Reject state-changing requests whose Origin isn't one of ours (CSRF defence)."""
    allowed = set((settings or get_settings()).allowed_origins)

    @app.middleware("http")
    async def _origin_guard(request: Request, call_next):
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            origin = request.headers.get("origin")
            if origin and origin.rstrip("/") not in allowed:
                return JSONResponse({"detail": "Origin not allowed."}, status_code=403)
        return await call_next(request)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _client_ip(request: Request) -> str:
    return request.client.host if request.client else ""


def _refresh_path(request: Request) -> str:
    """Path the browser uses for /auth: '/auth', or '/api/auth' behind the /api proxy."""
    prefix = (request.headers.get("x-forwarded-prefix") or "").rstrip("/")
    return (prefix if _PREFIX.fullmatch(prefix) else "") + REFRESH_PATH


def _set_session_cookies(response: Response, request: Request, access: str, refresh: str,
                         settings: Settings) -> None:
    common = {"httponly": True, "secure": settings.cookie_secure, "samesite": "lax"}
    response.set_cookie(ACCESS_COOKIE, access, max_age=settings.access_token_minutes * 60, path="/", **common)
    response.set_cookie(REFRESH_COOKIE, refresh, max_age=settings.refresh_token_days * 86400,
                        path=_refresh_path(request), **common)


def _clear_session_cookies(response: Response, request: Request, settings: Settings) -> None:
    common = {"httponly": True, "secure": settings.cookie_secure, "samesite": "lax"}
    response.delete_cookie(ACCESS_COOKIE, path="/", **common)
    response.delete_cookie(REFRESH_COOKIE, path=_refresh_path(request), **common)


def _start_session(db: Session, user: User, request: Request, response: Response,
                   settings: Settings) -> RefreshSession:
    raw = new_token()
    session = RefreshSession(
        user_id=user.id, token_hash=token_hash(raw),
        expires_at=utcnow() + timedelta(days=settings.refresh_token_days),
        user_agent=(request.headers.get("user-agent") or "")[:255], ip=_client_ip(request),
    )
    db.add(session)
    db.flush()
    _set_session_cookies(response, request, create_access_token(user.id, settings), raw, settings)
    return session


def _revoke_all_sessions(db: Session, user_id: str) -> None:
    db.execute(update(RefreshSession)
               .where(RefreshSession.user_id == user_id, RefreshSession.revoked_at.is_(None))
               .values(revoked_at=utcnow()))


def _issue_email_token(db: Session, user: User, purpose: str, lifetime: timedelta) -> str:
    # Only the newest link of a kind works: older unused ones are retired.
    db.execute(update(EmailToken)
               .where(EmailToken.user_id == user.id, EmailToken.purpose == purpose,
                      EmailToken.used_at.is_(None))
               .values(used_at=utcnow()))
    raw = new_token()
    db.add(EmailToken(user_id=user.id, purpose=purpose, token_hash=token_hash(raw),
                      expires_at=utcnow() + lifetime))
    return raw


def _consume_email_token(db: Session, raw: str, purpose: str) -> User:
    row = db.scalar(select(EmailToken).where(EmailToken.token_hash == token_hash(raw),
                                             EmailToken.purpose == purpose))
    if row is None or row.used_at is not None or as_utc(row.expires_at) < utcnow():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This link is invalid or has expired.")
    row.used_at = utcnow()
    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This link is invalid or has expired.")
    return user


def _send_verification(db: Session, user: User, mailer: mail.Mailer, settings: Settings) -> None:
    raw = _issue_email_token(db, user, "verify", timedelta(hours=settings.verify_token_hours))
    link = f"{settings.frontend_url}/verify-email?token={raw}"
    mailer.send(mail.verify_email_message(user.email, user.name, link, settings.verify_token_hours))


def _check_throttle(db: Session, email: str, ip: str, settings: Settings) -> None:
    since = utcnow() - timedelta(minutes=settings.failure_window_minutes)
    by_email = db.scalar(select(func.count()).select_from(LoginAttempt)
                         .where(LoginAttempt.email == email, LoginAttempt.at >= since))
    by_ip = db.scalar(select(func.count()).select_from(LoginAttempt)
                      .where(LoginAttempt.ip == ip, LoginAttempt.at >= since)) if ip else 0
    if by_email >= settings.max_failures_per_email or by_ip >= settings.max_failures_per_ip:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            f"Too many failed attempts. Try again in {settings.failure_window_minutes} minutes.",
                            headers={"Retry-After": str(settings.failure_window_minutes * 60)})


def _normalise_email(email: str) -> str:
    return email.strip().lower()


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def signup(body: SignupIn, request: Request, response: Response, db: Session = Depends(get_db),
           settings: Settings = Depends(settings_dep), mailer: mail.Mailer = Depends(mailer_dep)):
    email = _normalise_email(body.email)
    problem = password_problem(body.password, email)
    if problem:
        raise HTTPException(422, problem)
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")
    user = User(email=email, name=body.name, password_hash=hash_password(body.password))
    db.add(user)
    db.flush()
    _start_session(db, user, request, response, settings)
    _send_verification(db, user, mailer, settings)
    db.commit()
    return {"user": UserOut.of(user)}


@router.post("/login", response_model=UserResponse)
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db),
          settings: Settings = Depends(settings_dep)):
    email, ip = _normalise_email(body.email), _client_ip(request)
    _check_throttle(db, email, ip, settings)
    user = db.scalar(select(User).where(User.email == email))
    # Always run one hash verification, so unknown emails can't be told apart by timing
    ok = verify_password(user.password_hash if user else DUMMY_HASH, body.password)
    if not (user and ok and user.is_active):
        db.add(LoginAttempt(email=email, ip=ip))
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password.")
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
    db.execute(delete(LoginAttempt).where(LoginAttempt.email == email))
    _start_session(db, user, request, response, settings)
    db.commit()
    return {"user": UserOut.of(user)}


@router.post("/refresh", response_model=UserResponse)
def refresh(request: Request, response: Response, db: Session = Depends(get_db),
            settings: Settings = Depends(settings_dep)):
    def expired(clear: bool = True) -> JSONResponse:
        failure = JSONResponse({"detail": "Session expired. Please sign in again."}, status_code=401)
        if clear:
            _clear_session_cookies(failure, request, settings)
        return failure

    raw = request.cookies.get(REFRESH_COOKIE)
    session = db.scalar(select(RefreshSession).where(RefreshSession.token_hash == token_hash(raw))) if raw else None
    now = utcnow()
    if session is None or as_utc(session.expires_at) < now:
        return expired()
    if session.revoked_at is not None:
        rotated_recently = (session.replaced_by is not None
                            and (now - as_utc(session.revoked_at)).total_seconds() <= REUSE_GRACE_SECONDS)
        if rotated_recently:
            # Another tab just rotated it; that tab's new cookies are already in the
            # browser, so don't clear them.
            return expired(clear=False)
        if session.replaced_by is not None:
            _revoke_all_sessions(db, session.user_id)  # an old token came back: assume theft
            db.commit()
        return expired()
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        return expired()
    new_session = _start_session(db, user, request, response, settings)
    session.revoked_at, session.replaced_by = now, new_session.id
    db.commit()
    return {"user": UserOut.of(user)}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, db: Session = Depends(get_db), settings: Settings = Depends(settings_dep)):
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw:
        db.execute(update(RefreshSession)
                   .where(RefreshSession.token_hash == token_hash(raw), RefreshSession.revoked_at.is_(None))
                   .values(revoked_at=utcnow()))
        db.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_session_cookies(response, request, settings)
    return response


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_all(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db),
               settings: Settings = Depends(settings_dep)):
    _revoke_all_sessions(db, user.id)
    db.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_session_cookies(response, request, settings)
    return response


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)):
    return {"user": UserOut.of(user)}


@router.post("/verify-email", response_model=UserResponse)
def verify_email(body: TokenIn, db: Session = Depends(get_db)):
    user = _consume_email_token(db, body.token, "verify")
    if user.email_verified_at is None:
        user.email_verified_at = utcnow()
    db.commit()
    return {"user": UserOut.of(user)}


@router.post("/resend-verification", status_code=status.HTTP_202_ACCEPTED)
def resend_verification(user: User = Depends(get_current_user), db: Session = Depends(get_db),
                        settings: Settings = Depends(settings_dep), mailer: mail.Mailer = Depends(mailer_dep)):
    if not user.email_verified:
        _send_verification(db, user, mailer, settings)
        db.commit()
    return {"detail": "If your email isn't verified yet, a new link is on its way."}


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(body: EmailIn, request: Request, db: Session = Depends(get_db),
                    settings: Settings = Depends(settings_dep), mailer: mail.Mailer = Depends(mailer_dep)):
    email = _normalise_email(body.email)
    _check_throttle(db, email, _client_ip(request), settings)
    user = db.scalar(select(User).where(User.email == email))
    if user and user.is_active:
        raw = _issue_email_token(db, user, "reset", timedelta(minutes=settings.reset_token_minutes))
        link = f"{settings.frontend_url}/reset-password?token={raw}"
        mailer.send(mail.reset_password_message(user.email, user.name, link, settings.reset_token_minutes))
    # Counted like a failed login, so this can't be used to spam someone's inbox
    db.add(LoginAttempt(email=email, ip=_client_ip(request)))
    db.commit()
    # Same answer whether or not the account exists (no account enumeration)
    return {"detail": "If an account exists for this email, a reset link is on its way."}


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(body: ResetIn, request: Request, db: Session = Depends(get_db),
                   settings: Settings = Depends(settings_dep)):
    user = _consume_email_token(db, body.token, "reset")
    problem = password_problem(body.password, user.email)
    if problem:
        db.rollback()  # keep the link usable for a second try
        raise HTTPException(422, problem)
    user.password_hash = hash_password(body.password)
    user.email_verified_at = user.email_verified_at or utcnow()  # the link proves the inbox
    _revoke_all_sessions(db, user.id)  # sign out every device
    db.execute(delete(LoginAttempt).where(LoginAttempt.email == user.email))
    db.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_session_cookies(response, request, settings)
    return response


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(body: ChangePasswordIn, request: Request, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db), settings: Settings = Depends(settings_dep)):
    if not verify_password(user.password_hash, body.current_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is wrong.")
    problem = password_problem(body.new_password, user.email)
    if problem:
        raise HTTPException(422, problem)
    user.password_hash = hash_password(body.new_password)
    _revoke_all_sessions(db, user.id)  # other devices must sign in again...
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _start_session(db, user, request, response, settings)  # ...but not this one
    db.commit()
    return response
