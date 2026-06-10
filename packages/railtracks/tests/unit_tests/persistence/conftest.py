"""Shared fixtures for persistence tests.

`tmp_railtracks_home` redirects `resolve_railtracks_home()` to a tmp
directory so each test gets a fresh DB without touching the developer's
real `.railtracks/` workspace.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel

from railtracks.persistence.connection import get_engine


@pytest.fixture
def tmp_railtracks_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    # `resolve_railtracks_home()` reads RAILTRACKS_HOME and appends ".railtracks",
    # so the fixture mirrors that to match the path env.py will compute.
    monkeypatch.setenv("RAILTRACKS_HOME", str(tmp_path))
    home = tmp_path / ".railtracks"
    home.mkdir(parents=True, exist_ok=True)
    return home


@pytest.fixture
def engine(tmp_railtracks_home: Path) -> Iterator[Engine]:
    eng = get_engine(tmp_railtracks_home)
    SQLModel.metadata.create_all(eng)
    try:
        yield eng
    finally:
        eng.dispose()


@pytest.fixture
def db_session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as session:
        yield session
