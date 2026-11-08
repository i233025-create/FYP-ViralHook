"""Alembic environment: runs migrations against the URL set by backend.db.migrate()
(or DATABASE_URL / the development default when run from the alembic CLI)."""

from alembic import context
from sqlalchemy import pool

from backend import models  # noqa: F401  (registers the tables on Base.metadata)
from backend.config import get_settings
from backend.db import Base, make_engine

config = context.config
target_metadata = Base.metadata


def _url() -> str:
    return config.get_main_option("sqlalchemy.url") or get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True,
                      render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = make_engine(_url())
    with engine.connect() as connection:
        # render_as_batch: lets ALTER-style migrations work on SQLite too
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
