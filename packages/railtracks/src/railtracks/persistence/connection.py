"""SQLite engine factory for railtracks persistence.

The workspace DB lives at ``<railtracks_home>/data/railtracks.db``. WAL
mode is enabled so concurrent writers/readers do not block; foreign
keys are enforced (off by default in SQLite); ``synchronous=NORMAL`` is
a safe-enough setting that pairs well with WAL.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine

from railtracks.paths import resolve_railtracks_home

_ALEMBIC_INI = (
    Path(__file__).resolve().parents[3] / "alembic.ini"
)


def database_path(railtracks_home: Path | None = None) -> Path:
    home = railtracks_home if railtracks_home is not None else resolve_railtracks_home()
    return home / "data" / "railtracks.db"


def database_url(railtracks_home: Path | None = None) -> str:
    return f"sqlite:///{database_path(railtracks_home)}"


def get_engine(
    railtracks_home: Path | None = None,
    *,
    echo: bool = False,
) -> Engine:
    db_path = database_path(railtracks_home)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", echo=echo, future=True)
    _attach_sqlite_pragmas(engine)
    return engine


def alembic_config_path() -> Path:
    """Return the path to the package's ``alembic.ini``.

    Used by tests, the CLI ``migrate-json-to-sqlite`` subcommand, and any
    code that needs to run migrations programmatically.
    """
    return _ALEMBIC_INI


def _attach_sqlite_pragmas(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA synchronous=NORMAL")
        finally:
            cursor.close()
