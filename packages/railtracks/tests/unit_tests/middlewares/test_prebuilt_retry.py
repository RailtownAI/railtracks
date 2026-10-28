"""Unit tests for the prebuilt Retry middleware: `rt.prebuilt.middleware.Retry`.

Retry is slot-agnostic — it only re-invokes `call` — so the tests wire it
directly via `.wrap(fake_call)` and through decision nodes.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import litellm
import pytest
import railtracks as rt
from railtracks.exceptions import (
    DecisionAuthenticationError,
    DecisionModelError,
    DecisionRateLimitError,
    DecisionRefusalError,
    DecisionTimeoutError,
    LLMError,
)
from railtracks.llm._exceptions import RetryError
from railtracks.llm.retries import ExponentialRetry, FixedRetry
from railtracks.middleware import Middleware
from railtracks.prebuilt.middleware import Retry

from ..decisions.conftest import Triage, respond


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


@pytest.fixture
def decision_model(monkeypatch):
    provider_call = AsyncMock()
    monkeypatch.setattr(litellm, "adecisions", provider_call)
    model = rt.decisions.TypeSafeDecisions("jev-latest", api_key="test-key")
    return model, provider_call


@pytest.mark.parametrize("provider_error", [litellm.Timeout, litellm.RateLimitError])
async def test_decision_node_retries_with_default_retry_on(
    decision_model, provider_error
):
    model, provider_call = decision_model
    provider_call.side_effect = [
        provider_error(
            message="transient", llm_provider="typesafe", model="jev-latest"
        ),
        provider_error(
            message="transient", llm_provider="typesafe", model="jev-latest"
        ),
        respond(),
    ]
    node = rt.decision_node(model=model, schema=Triage, middleware=[_no_sleep_retry()])

    result = await rt.Flow(name="Retry decisions", entry_point=node).ainvoke("Help!")

    assert result.structured["department"].choice == "technical"
    assert provider_call.await_count == 3


@pytest.mark.parametrize("custom_retry_on", [False, True])
@pytest.mark.parametrize(
    "provider_error, node_error",
    [
        (litellm.Timeout, DecisionTimeoutError),
        (litellm.RateLimitError, DecisionRateLimitError),
    ],
)
async def test_decision_node_exhaustion_preserves_last_error(
    decision_model, provider_error, node_error, custom_retry_on
):
    model, provider_call = decision_model
    provider_call.side_effect = [
        provider_error(
            message=f"attempt {i}", llm_provider="typesafe", model="jev-latest"
        )
        for i in range(3)
    ]
    retry = (
        _no_sleep_retry(retry_on=(node_error,))
        if custom_retry_on
        else _no_sleep_retry()
    )
    node = rt.decision_node(model=model, schema=Triage, middleware=[retry])

    with pytest.raises(DecisionModelError) as exc:
        await rt.Flow(name="Retry decisions", entry_point=node).ainvoke("Help!")

    assert type(exc.value) is node_error
    assert provider_call.await_count == 3
    history = exc.value.__cause__
    assert isinstance(history, RetryError)
    assert len(history.exception_list) == 3
    assert all(type(error) is node_error for error in history.exception_list)
    assert exc.value is history.exception_list[-1]
    assert "attempt 2" in exc.value.reason


@pytest.mark.parametrize(
    "error",
    [
        DecisionAuthenticationError("bad key"),
        DecisionRefusalError("refused", refused=["question"], answers={}),
        DecisionModelError("other failure"),
    ],
)
async def test_non_transient_decision_errors_are_not_retried(error):
    call = AsyncMock(side_effect=error)

    with pytest.raises(type(error)) as exc:
        await _no_sleep_retry().wrap(call)()

    assert exc.value is error
    assert call.await_count == 1


@pytest.mark.parametrize("retry_on", [(), (ValueError,)])
async def test_custom_retry_on_replaces_decision_defaults(retry_on):
    error = DecisionTimeoutError("timed out")
    call = AsyncMock(side_effect=error)

    with pytest.raises(DecisionTimeoutError) as exc:
        await _no_sleep_retry(retry_on=retry_on).wrap(call)()

    assert exc.value is error
    assert call.await_count == 1


async def test_agent_node_exhaustion_still_raises_retry_error(mock_llm):
    agent = rt.agent_node(
        "Retried Agent",
        llm=mock_llm(errors=[_rate_limit_error] * 3),
        middleware=[_no_sleep_retry(retry_on=(LLMError,))],
    )

    with pytest.raises(RetryError) as exc:
        await rt.Flow(name="Retry agent", entry_point=agent).ainvoke("Hello")

    assert len(exc.value.exception_list) == 3
    assert all(isinstance(error, LLMError) for error in exc.value.exception_list)
