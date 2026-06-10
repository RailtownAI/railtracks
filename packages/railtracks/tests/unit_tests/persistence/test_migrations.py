"""Verify Alembic upgrade/downgrade round-trip."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from railtracks.persistence.connection import (
    alembic_config_path,
    get_engine,
)

EXPECTED_TABLES = {
    "sessions",
    "runs",
    "nodes",
    "node_versions",
    "stamps",
    "requests",
    "failures",
    "llm_calls",
    "messages",
    "tool_calls",
    "tool_responses",
    "guardrails",
    "evaluations",
    "memory",
    "middleware_traces",
}


def _alembic_config(railtracks_home: Path) -> Config:
    # The URL in alembic.ini is a placeholder; env.py computes the real URL
    # from resolve_railtracks_home() at runtime. RAILTRACKS_HOME is set by the
    # tmp_railtracks_home fixture, so env.py picks up the tmp DB path.
    return Config(str(alembic_config_path()))


def test_upgrade_head_creates_every_table(tmp_railtracks_home: Path) -> None:
    cfg = _alembic_config(tmp_railtracks_home)
    command.upgrade(cfg, "head")

    engine = get_engine(tmp_railtracks_home)
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    # alembic_version is created by Alembic itself; ignore.
    tables.discard("alembic_version")
    assert tables == EXPECTED_TABLES


def test_downgrade_to_base_drops_every_table(tmp_railtracks_home: Path) -> None:
    cfg = _alembic_config(tmp_railtracks_home)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")

    engine = get_engine(tmp_railtracks_home)
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    tables.discard("alembic_version")
    assert tables == set()
