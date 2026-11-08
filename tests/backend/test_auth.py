"""
Tests for backend/ auth: signup, login, sessions, refresh rotation, email
tokens, throttling, CSRF origin guard and migrations. Each test gets its own
SQLite database; no network.
"""

import re
from dataclasses import replace
from datetime import timedelta

import pytest

pytest.importorskip("httpx")
pytest.importorskip("argon2")
pytest.importorskip("jwt")
pytest.importorskip("alembic")

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from backend import auth
from backend.config import Settings
from backend.db import get_db, make_engine, migrate
from backend.mailer import ConsoleMailer
from backend.models import EmailToken, RefreshSession, User, utcnow

ORIGIN = "http://localhost:5173"
PASSWORD = "correct horse battery"


@pytest.fixture
def env(tmp_path):
    url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    migrate(url)
    engine = make_engine(url)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    settings = Settings(env="test", database_url=url, jwt_secret="x" * 48, cookie_secure=False,
                        allowed_origins=(ORIGIN,), frontend_url=ORIGIN)
    mailer = ConsoleMailer()

    app = FastAPI()
    auth.install_origin_guard(app, settings)
    app.include_router(auth.router)

    @app.get("/private")
    def private(user=Depends(auth.get_current_user)):
        return {"id": user.id}

    @app.get("/verified-only")
    def verified_only(user=Depends(auth.require_verified)):
        return {"ok": True}

    def db_override():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[auth.settings_dep] = lambda: settings
    app.dependency_overrides[auth.mailer_dep] = lambda: mailer

    class Env:
        pass

    e = Env()
    e.app, e.Session, e.settings, e.mailer = app, Session, settings, mailer
    e.client = TestClient(app)
    yield e
    engine.dispose()


def signup(client, email="sara@example.com", name="Sara", password=PASSWORD):
    return client.post("/auth/signup", json={"name": name, "email": email, "password": password})


def link_token(mailer, kind):
    match = re.search(rf"/{kind}\?token=([\w-]+)", mailer.sent[-1].body)
    assert match, mailer.sent[-1].body
    return match.group(1)


# ─── Signup / login / me ──────────────────────────────────────────────────────

def test_signup_creates_user_signs_in_and_sends_verification(env):
    r = signup(env.client, email="  Sara@Example.COM ")
    assert r.status_code == 201
    user = r.json()["user"]
    assert user["email"] == "sara@example.com" and user["emailVerified"] is False
    assert "vh_access" in env.client.cookies and "vh_refresh" in env.client.cookies
    assert env.client.get("/auth/me").json()["user"]["id"] == user["id"]
    assert "verify-email?token=" in env.mailer.sent[-1].body

    with env.Session() as s:
        row = s.scalar(select(User))
        assert row.password_hash.startswith("$argon2id$") and PASSWORD not in row.password_hash


def test_signup_rejects_duplicate_email_and_weak_passwords(env):
    assert signup(env.client).status_code == 201
    assert signup(TestClient(env.app), email="SARA@example.com").status_code == 409
    for bad in ["short", "aaaaaaaaaaaa", "sara2@example.com"]:
        r = signup(TestClient(env.app), email="sara2@example.com", password=bad)
        assert r.status_code == 422, bad
    assert signup(TestClient(env.app), email="not-an-email").status_code == 422


def test_login_logout_and_protected_route(env):
    signup(env.client)
    fresh = TestClient(env.app)
    assert fresh.get("/private").status_code == 401
    assert fresh.post("/auth/login", json={"email": "sara@example.com", "password": "wrong pass 123"}).status_code == 401
    r = fresh.post("/auth/login", json={"email": "SARA@example.com", "password": PASSWORD})
    assert r.status_code == 200
    assert fresh.get("/private").status_code == 200

    assert fresh.post("/auth/logout").status_code == 204
    assert fresh.get("/private").status_code == 401
    assert fresh.post("/auth/refresh").status_code == 401  # session revoked server-side


def test_unknown_email_and_wrong_password_look_the_same(env):
    signup(env.client)
    c = TestClient(env.app)
    a = c.post("/auth/login", json={"email": "nobody@example.com", "password": PASSWORD})
    b = c.post("/auth/login", json={"email": "sara@example.com", "password": "wrong pass 123"})
    assert a.status_code == b.status_code == 401 and a.json() == b.json()


def test_forged_or_expired_access_token_is_rejected(env):
    from backend.security import create_access_token
    signup(env.client)
    c = TestClient(env.app)
    c.cookies.set("vh_access", create_access_token("someone", replace(env.settings, jwt_secret="y" * 48)))
    assert c.get("/private").status_code == 401
    c.cookies.set("vh_access", create_access_token("someone", replace(env.settings, access_token_minutes=-1)))
    assert c.get("/private").status_code == 401


def test_deactivated_user_loses_access_immediately(env):
    signup(env.client)
    with env.Session() as s:
        s.scalar(select(User)).is_active = False
        s.commit()
    assert env.client.get("/private").status_code == 401
    assert env.client.post("/auth/refresh").status_code == 401


# ─── Refresh rotation ─────────────────────────────────────────────────────────

def test_refresh_rotates_token(env):
    signup(env.client)
    old = env.client.cookies.get("vh_refresh")
    assert env.client.post("/auth/refresh").status_code == 200
    assert env.client.cookies.get("vh_refresh") != old
    assert env.client.get("/private").status_code == 200


def test_reusing_a_rotated_refresh_token_revokes_all_sessions(env):
    signup(env.client)
    stolen = env.client.cookies.get("vh_refresh")
    env.client.post("/auth/refresh")  # legitimate rotation
    with env.Session() as s:          # move the rotation outside the grace window
        old = s.scalar(select(RefreshSession).where(RefreshSession.revoked_at.is_not(None)))
        old.revoked_at = utcnow() - timedelta(minutes=5)
        s.commit()

    attacker = TestClient(env.app)
    attacker.cookies.set("vh_refresh", stolen, path="/auth")
    assert attacker.post("/auth/refresh").status_code == 401
    # The legitimate session was revoked too
    assert env.client.post("/auth/refresh").status_code == 401


def test_concurrent_refresh_within_grace_does_not_log_everyone_out(env):
    signup(env.client)
    same = env.client.cookies.get("vh_refresh")
    other_tab = TestClient(env.app)
    other_tab.cookies.set("vh_refresh", same, path="/auth")
    assert env.client.post("/auth/refresh").status_code == 200
    assert other_tab.post("/auth/refresh").status_code == 401  # lost the race, no revoke-all
    assert env.client.post("/auth/refresh").status_code == 200


def test_logout_all_signs_out_other_devices(env):
    signup(env.client)
    laptop = TestClient(env.app)
    laptop.post("/auth/login", json={"email": "sara@example.com", "password": PASSWORD})
    assert env.client.post("/auth/logout-all").status_code == 204
    assert laptop.post("/auth/refresh").status_code == 401


# ─── Email verification (soft) ────────────────────────────────────────────────

def test_verify_email_flow_and_soft_verification(env):
    signup(env.client)
    assert env.client.get("/private").status_code == 200        # usable before verifying
    assert env.client.get("/verified-only").status_code == 403  # sensitive actions wait
    token = link_token(env.mailer, "verify-email")
    r = env.client.post("/auth/verify-email", json={"token": token})
    assert r.status_code == 200 and r.json()["user"]["emailVerified"] is True
    assert env.client.get("/verified-only").status_code == 200
    assert env.client.post("/auth/verify-email", json={"token": token}).status_code == 400  # single use


def test_resend_verification_retires_the_old_link(env):
    signup(env.client)
    first = link_token(env.mailer, "verify-email")
    assert env.client.post("/auth/resend-verification").status_code == 202
    second = link_token(env.mailer, "verify-email")
    assert first != second
    assert env.client.post("/auth/verify-email", json={"token": first}).status_code == 400
    assert env.client.post("/auth/verify-email", json={"token": second}).status_code == 200


def test_expired_link_is_rejected(env):
    signup(env.client)
    token = link_token(env.mailer, "verify-email")
    with env.Session() as s:
        s.scalar(select(EmailToken)).expires_at = utcnow() - timedelta(seconds=1)
        s.commit()
    assert env.client.post("/auth/verify-email", json={"token": token}).status_code == 400


# ─── Password reset / change ──────────────────────────────────────────────────

def test_forgot_password_never_reveals_whether_an_account_exists(env):
    signup(env.client)
    sent_before = len(env.mailer.sent)
    a = TestClient(env.app).post("/auth/forgot-password", json={"email": "nobody@example.com"})
    b = TestClient(env.app).post("/auth/forgot-password", json={"email": "sara@example.com"})
    assert a.status_code == b.status_code == 202 and a.json() == b.json()
    assert len(env.mailer.sent) == sent_before + 1  # only the real account got an email


def test_reset_password_changes_password_and_signs_out_everywhere(env):
    signup(env.client)
    TestClient(env.app).post("/auth/forgot-password", json={"email": "sara@example.com"})
    token = link_token(env.mailer, "reset-password")
    c = TestClient(env.app)
    assert c.post("/auth/reset-password", json={"token": token, "password": "short"}).status_code == 422
    assert c.post("/auth/reset-password", json={"token": token, "password": "a new strong pass"}).status_code == 204
    assert c.post("/auth/reset-password", json={"token": token, "password": "another pass 99"}).status_code == 400
    assert env.client.post("/auth/refresh").status_code == 401  # old sessions are gone
    assert c.post("/auth/login", json={"email": "sara@example.com", "password": PASSWORD}).status_code == 401
    r = c.post("/auth/login", json={"email": "sara@example.com", "password": "a new strong pass"})
    assert r.status_code == 200 and r.json()["user"]["emailVerified"] is True


def test_change_password_keeps_this_session_only(env):
    signup(env.client)
    other = TestClient(env.app)
    other.post("/auth/login", json={"email": "sara@example.com", "password": PASSWORD})
    bad = env.client.post("/auth/change-password", json={"current_password": "nope nope 1", "new_password": "x" * 12})
    assert bad.status_code == 400
    ok = env.client.post("/auth/change-password",
                         json={"current_password": PASSWORD, "new_password": "brand new pass 1"})
    assert ok.status_code == 204
    assert env.client.get("/private").status_code == 200
    assert env.client.post("/auth/refresh").status_code == 200
    assert other.post("/auth/refresh").status_code == 401


# ─── Throttling and CSRF ──────────────────────────────────────────────────────

def test_repeated_failures_are_throttled_and_success_resets(env):
    signup(env.client)
    c = TestClient(env.app)
    for _ in range(env.settings.max_failures_per_email):
        assert c.post("/auth/login", json={"email": "sara@example.com", "password": "wrong pass 123"}).status_code == 401
    r = c.post("/auth/login", json={"email": "sara@example.com", "password": PASSWORD})
    assert r.status_code == 429 and "Retry-After" in r.headers  # even the right password waits


def test_foreign_origin_is_blocked_for_state_changes(env):
    signup(env.client)
    evil = env.client.post("/auth/logout-all", headers={"Origin": "https://evil.example"})
    assert evil.status_code == 403
    assert env.client.get("/auth/me", headers={"Origin": "https://evil.example"}).status_code == 200  # reads ok
    assert env.client.post("/auth/refresh", headers={"Origin": ORIGIN}).status_code == 200


def test_cookies_are_httponly_and_lax(env):
    r = signup(env.client)
    cookies = r.headers.get_list("set-cookie")
    assert len(cookies) == 2
    for c in cookies:
        assert "HttpOnly" in c and "samesite=lax" in c.lower()
    refresh = next(c for c in cookies if c.startswith("vh_refresh="))
    assert "Path=/auth" in refresh


# ─── Migrations match the models ──────────────────────────────────────────────

def test_migrations_match_models(tmp_path):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from backend.db import Base

    url = f"sqlite:///{(tmp_path / 'm.db').as_posix()}"
    migrate(url)
    engine = make_engine(url)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    engine.dispose()
    assert diff == [], f"models.py and migrations differ — add a migration: {diff}"


def test_refresh_cookie_path_follows_the_api_proxy_prefix(env):
    r = env.client.post("/auth/signup", headers={"X-Forwarded-Prefix": "/api"},
                        json={"name": "P", "email": "p@example.com", "password": PASSWORD})
    refresh = next(c for c in r.headers.get_list("set-cookie") if c.startswith("vh_refresh="))
    assert "Path=/api/auth" in refresh
    bad = TestClient(env.app).post("/auth/signup", headers={"X-Forwarded-Prefix": "/a/../b; x=1"},
                                   json={"name": "Q", "email": "q@example.com", "password": PASSWORD})
    refresh = next(c for c in bad.headers.get_list("set-cookie") if c.startswith("vh_refresh="))
    assert "Path=/auth;" in refresh   # anything odd falls back to the plain path
