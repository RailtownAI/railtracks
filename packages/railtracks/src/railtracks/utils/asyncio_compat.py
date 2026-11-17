"""Helpers for calling async code from synchronous entry points."""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextvars
from collections.abc import Coroutine
from typing import Any, TypeVar

_T = TypeVar("_T")


def run_sync(coro: Coroutine[Any, Any, _T]) -> _T:
    """
    Run ``coro`` to completion from synchronous code and return its result.

    With no event loop running in this thread, this is ``asyncio.run(coro)``.
    Inside a running loop (a notebook, an async framework), ``asyncio.run``
    would fail, so the coroutine runs on a worker thread with its own loop
    while the caller blocks; ``contextvars.copy_context()`` keeps the
    caller's context variables visible there.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    ctx = contextvars.copy_context()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(ctx.run, asyncio.run, coro).result()
