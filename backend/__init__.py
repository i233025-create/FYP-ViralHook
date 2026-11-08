"""
backend — product layer of the ViralHook API (users, auth, per-user data).

  config.py    settings from environment variables
  db.py        SQLAlchemy engine/session, Alembic migrations on startup
  models.py    User, RefreshSession, EmailToken, LoginAttempt
  security.py  password hashing (argon2), JWT access tokens, opaque tokens
  mailer.py    email interface (console in development, SMTP later)
  auth.py      /auth routes + get_current_user dependency
  workspace.py per-user data folders

server.py mounts these routers; the AI pipeline stays in pipeline/ and the
modules.
"""
