"""Unit tests for the prebuilt MaxCalls middleware."""

from __future__ import annotations

import pytest
from railtracks.middleware import Middleware
from railtracks.prebuilt.middleware.max_calls import MaxCalls


def test_max_calls_is_a_plain_middleware():
    assert isinstance(MaxCalls(1), Middleware)


@pytest.mark.asyncio
async def test_calls_within_the_limit_succeed():
    async def add(x, *, y):
        return x + y

    max_calls = MaxCalls(2)

    assert await max_calls.wrap(add)(2, y=3) == 5
    assert await max_calls.wrap(add)(4, y=5) == 9


@pytest.mark.asyncio
async def test_call_beyond_the_limit_raises():
    async def add(x, y):
        return x + y

    max_calls = MaxCalls(1)
    await max_calls.wrap(add)(1, 2)

    with pytest.raises(Exception, match="Maximum number of calls exceeded"):
        await max_calls.wrap(add)(1, 2)


@pytest.mark.asyncio
async def test_custom_message_is_used_when_limit_exceeded():
    async def noop():
        return None

    max_calls = MaxCalls(0, custom_message="budget exhausted")

    with pytest.raises(Exception, match="budget exhausted"):
        await max_calls.wrap(noop)()


@pytest.mark.asyncio
async def test_count_is_not_incremented_once_limit_is_hit():
    async def noop():
        return None

    max_calls = MaxCalls(0)

    for _ in range(3):
        with pytest.raises(Exception, match="Maximum number of calls exceeded"):
            await max_calls.wrap(noop)()

    assert max_calls._call_count == 0


@pytest.mark.asyncio
async def test_wrapped_exception_propagates_and_still_counts_the_call():
    async def broken():
        raise ValueError("broken")

    max_calls = MaxCalls(2)

    with pytest.raises(ValueError, match="broken"):
        await max_calls.wrap(broken)()

    assert max_calls._call_count == 1
