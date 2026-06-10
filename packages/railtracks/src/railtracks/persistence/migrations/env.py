"""Alembic environment for railtracks persistence.

The database URL is computed at runtime from `resolve_railtracks_home()`
rather than read from `alembic.ini` so the same env works regardless of
where the user runs `alembic` from.

Models are imported lazily — they register themselves on
`SQLModel.metadata` at import time. The import is wrapped in try/except
so the env still loads in early-scaffold states where `models.py` does
not yet exist.
"""

from __future__ import annotations

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from railtracks.paths import resolve_railtracks_home

try:
    from railtracks.persistence import models  # noqa: F401  # registers tables
except ImportError:
    pass

config = context.config

target_metadata = SQLModel.metadata


def _database_url() -> str:
    db_path = resolve_railtracks_home() / "data" / "railtracks.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path}"


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
