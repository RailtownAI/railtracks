"""Unit tests for the prebuilt Retry middleware: `rt.prebuilt.middleware.Retry`.

Retry is slot-agnostic — it only re-invokes `call` — so most tests wire it
directly via `.wrap(fake_call)` with arbitrary signatures; the rest run it as an
agent's model middleware, with only `litellm.completion` patched.
"""

from __future__ import annotations

from unittest.mock import patch

import litellm
import pytest
import railtracks as rt
from litellm.utils import ModelResponse
from railtracks.exceptions import LLMRateLimitError
from railtracks.llm._exceptions import RetryError
from railtracks.llm.retries import ExponentialRetry, FixedRetry
from railtracks.middleware import Middleware
from railtracks.prebuilt.middleware import Retry


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


def _timeout_error() -> litellm.exceptions.Timeout:
    return litellm.exceptions.Timeout(
        message="timed out", llm_provider="openai", model="gpt-6-luna"
    )


def _flaky_completion(error_factory, failures, calls):
    def completion(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] <= failures:
            raise error_factory()
        return ModelResponse(
            choices=[
                {
                    "message": {"content": "hello", "role": "assistant"},
                    "finish_reason": "stop",
                }
            ]
        )

    return completion


@pytest.mark.parametrize("error_factory", [_rate_limit_error, _timeout_error])
async def test_model_middleware_retries_a_provider_error(error_factory):
    calls = {"n": 0}
    agent = rt.agent_node(
        "Agent",
        llm=rt.llm.OpenAILLM("gpt-6-luna"),
        model_middleware=[_no_sleep_retry()],
    )

    with patch.object(
        litellm, "completion", side_effect=_flaky_completion(error_factory, 2, calls)
    ):
        result = await rt.Flow(name="Retry model", entry_point=agent).ainvoke("Hello")

    assert result.text == "hello"
    assert calls["n"] == 3


async def test_model_middleware_does_not_restart_an_exhausted_retry_approach():
    calls = {"n": 0}
    agent = rt.agent_node(
        "Agent",
        llm=rt.llm.OpenAILLM(
            "gpt-6-luna", retry_approach=FixedRetry(max_tries=3, delay=0.0)
        ),
        model_middleware=[_no_sleep_retry()],
    )

    with patch.object(
        litellm,
        "completion",
        side_effect=_flaky_completion(_rate_limit_error, 20, calls),
    ):
        with pytest.raises(LLMRateLimitError):
            await rt.Flow(name="Stacked retries", entry_point=agent).ainvoke("Hello")

    assert calls["n"] == 3
