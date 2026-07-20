"""Unit tests for the prebuilt Retry middleware: `rt.middleware.Retry`.

Retry is slot-agnostic — it only re-invokes `call` — so the tests wire it
directly via `.wrap(fake_call)` with arbitrary signatures.
"""

from __future__ import annotations

import litellm
import pytest
from railtracks.llm._exceptions import RetryError
from railtracks.llm.retries import ExponentialRetry, FixedRetry
from railtracks.middleware import Middleware, Retry


def _rate_limit_error() -> litellm.exceptions.RateLimitError:
    return litellm.exceptions.RateLimitError(
        message="rate limited", llm_provider="openai", model="gpt-4o"
    )


def _no_sleep_retry(max_tries: int = 3, **kwargs) -> Retry:
    return Retry(approach=FixedRetry(max_tries=max_tries, delay=0.0), **kwargs)


def test_retry_is_a_plain_middleware():
    assert isinstance(Retry(), Middleware)


def test_default_approach_is_exponential():
    assert isinstance(Retry(max_tries=5)._approach, ExponentialRetry)


@pytest.mark.asyncio
async def test_succeeds_after_transient_failures():
    calls = {"n": 0}

    async def flaky(x, y):
        calls["n"] += 1
        if calls["n"] < 3:
            raise _rate_limit_error()
        return x + y

    result = await _no_sleep_retry(max_tries=3).wrap(flaky)(1, 2)

    assert result == 3
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_exhausted_attempts_raise_retry_error():
    calls = {"n": 0}

    async def always_rate_limited():
        calls["n"] += 1
        raise _rate_limit_error()

    with pytest.raises(RetryError):
        await _no_sleep_retry(max_tries=3).wrap(always_rate_limited)()

    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_non_retryable_exception_propagates_immediately():
    calls = {"n": 0}

    async def broken():
        calls["n"] += 1
        raise ValueError("permanent bug, not a transient error")

    with pytest.raises(ValueError):
        await _no_sleep_retry(max_tries=3).wrap(broken)()

    assert calls["n"] == 1  # never retried


@pytest.mark.asyncio
async def test_custom_retry_on_widens_the_retryable_set():
    calls = {"n": 0}

    async def flaky_node():
        calls["n"] += 1
        if calls["n"] < 2:
            raise ValueError("transient in this domain")
        return "ok"

    retry = _no_sleep_retry(max_tries=3, retry_on=(ValueError,))
    assert await retry.wrap(flaky_node)() == "ok"
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_kwargs_are_forwarded_on_every_attempt():
    seen = []

    async def flaky(*, tag):
        seen.append(tag)
        if len(seen) < 2:
            raise _rate_limit_error()
        return tag

    result = await _no_sleep_retry(max_tries=2).wrap(flaky)(tag="hello")

    assert result == "hello"
    assert seen == ["hello", "hello"]
