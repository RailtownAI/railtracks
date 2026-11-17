from __future__ import annotations

import asyncio
import contextvars
import threading

import pytest
from railtracks.utils.asyncio_compat import run_sync

_marker: contextvars.ContextVar[str] = contextvars.ContextVar(
    "_marker", default="unset"
)


async def _double(x: int) -> int:
    await asyncio.sleep(0)
    return x * 2


async def _read_marker() -> str:
    return _marker.get()


async def _raise() -> None:
    raise ValueError("boom")


def test_run_sync_without_running_loop():
    assert run_sync(_double(21)) == 42


async def test_run_sync_inside_running_loop_uses_worker_thread():
    caller = threading.get_ident()
    seen: list[int] = []

    async def _where() -> int:
        seen.append(threading.get_ident())
        return 1

    assert run_sync(_where()) == 1
    assert seen and seen[0] != caller


async def test_run_sync_inside_running_loop_copies_contextvars():
    token = _marker.set("from-caller")
    try:
        assert run_sync(_read_marker()) == "from-caller"
    finally:
        _marker.reset(token)


async def test_run_sync_propagates_exceptions_inside_running_loop():
    with pytest.raises(ValueError, match="boom"):
        run_sync(_raise())


def test_run_sync_propagates_exceptions_without_running_loop():
    with pytest.raises(ValueError, match="boom"):
        run_sync(_raise())
