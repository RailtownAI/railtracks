"""Unit tests for the prebuilt Timeout middleware."""

from __future__ import annotations

import asyncio

import pytest
from railtracks.middleware import Middleware
from railtracks.prebuilt.middleware import Timeout


def test_timeout_is_a_plain_middleware():
    assert isinstance(Timeout(1), Middleware)


@pytest.mark.asyncio
async def test_returns_result_before_deadline():
    async def add(x, *, y):
        return x + y

    result = await Timeout(1).wrap(add)(2, y=3)

    assert result == 5


@pytest.mark.asyncio
async def test_raises_timeout_error_and_cancels_call():
    cancelled = asyncio.Event()

    async def slow_call():
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.set()

    with pytest.raises(asyncio.TimeoutError):
        await Timeout(0.01).wrap(slow_call)()

    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_wrapped_exception_propagates():
    async def broken():
        raise ValueError("broken")

    with pytest.raises(ValueError, match="broken"):
        await Timeout(1).wrap(broken)()
