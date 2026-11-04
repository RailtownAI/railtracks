"""Unit tests for the prebuilt Retry middleware: `rt.prebuilt.middleware.Retry`.

Retry is slot-agnostic — it only re-invokes `call` — so most tests wire it
directly via `.wrap(fake_call)` with arbitrary signatures; the rest run it on an
agent node.
"""

from __future__ import annotations

from unittest.mock import patch

import litellm
import pytest
import railtracks as rt
from litellm.utils import ModelResponse
from railtracks.exceptions import LLMRateLimitError, LLMTimeoutError
from railtracks.llm._exceptions import (
    ProviderRateLimitError,
    ProviderTimeoutError,
    RetryError,
)
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


def _counting(factory, calls):
    def make():
        calls["n"] += 1
        return factory()

    return make


@pytest.mark.parametrize(
    "provider_error", [ProviderRateLimitError, ProviderTimeoutError]
)
async def test_agent_node_retries_with_default_retry_on(mock_llm, provider_error):
    calls = {"n": 0}
    llm = mock_llm(errors=[_counting(lambda: provider_error("transient"), calls)] * 2)
    agent = rt.agent_node("Agent", llm=llm, middleware=[_no_sleep_retry()])

    result = await rt.Flow(name="Retry agent", entry_point=agent).ainvoke("Hello")

    assert result.text == "mocked Message"
    assert calls["n"] == 2


@pytest.mark.parametrize(
    "provider_error, node_error",
    [
        (ProviderRateLimitError, LLMRateLimitError),
        (ProviderTimeoutError, LLMTimeoutError),
    ],
)
async def test_agent_node_exhaustion_raises_retry_error(
    mock_llm, provider_error, node_error
):
    calls = {"n": 0}
    llm = mock_llm(errors=[_counting(lambda: provider_error("transient"), calls)] * 5)
    agent = rt.agent_node("Agent", llm=llm, middleware=[_no_sleep_retry()])

    with pytest.raises(RetryError) as exc:
        await rt.Flow(name="Retry agent", entry_point=agent).ainvoke("Hello")

    assert calls["n"] == 3
    assert [type(e) for e in exc.value.exception_list] == [node_error] * 3


@pytest.mark.parametrize("model_layer", ["retry_approach", "model_middleware"])
async def test_node_retry_does_not_restart_an_exhausted_model_retry(
    mock_llm, model_layer
):
    calls = {"n": 0}
    llm = mock_llm(
        errors=[_counting(_rate_limit_error, calls)] * 20,
        retry_approach=(
            FixedRetry(max_tries=3, delay=0.0)
            if model_layer == "retry_approach"
            else None
        ),
    )
    agent = rt.agent_node(
        "Agent",
        llm=llm,
        middleware=[_no_sleep_retry()],
        model_middleware=(
            [_no_sleep_retry()] if model_layer == "model_middleware" else None
        ),
    )

    with pytest.raises(LLMRateLimitError) as exc:
        await rt.Flow(name="Stacked retries", entry_point=agent).ainvoke("Hello")

    assert calls["n"] == 3
    assert exc.value.retry_exhausted


async def test_exhausted_error_propagates_even_with_broad_retry_on():
    calls = {"n": 0}
    exhausted = LLMRateLimitError("rate limited")
    exhausted.retry_exhausted = True

    async def already_retried():
        calls["n"] += 1
        raise exhausted

    with pytest.raises(LLMRateLimitError) as exc:
        await _no_sleep_retry(retry_on=(Exception,)).wrap(already_retried)()

    assert exc.value is exhausted
    assert calls["n"] == 1


def _provider_failure(error_type):
    return error_type(message="transient", llm_provider="openai", model="gpt-4o")


def _ok_completion() -> ModelResponse:
    return ModelResponse(
        choices=[
            {"message": {"content": "ok", "role": "assistant"}, "finish_reason": "stop"}
        ]
    )


def _openai_agent(**middleware):
    return rt.agent_node(
        "Agent", llm=rt.llm.OpenAILLM("gpt-4o", api_key="test-key"), **middleware
    )


@pytest.mark.parametrize("error_type", [litellm.RateLimitError, litellm.Timeout])
async def test_model_middleware_retries_translated_provider_errors(error_type):
    agent = _openai_agent(model_middleware=[_no_sleep_retry()])
    side_effect = [_provider_failure(error_type)] * 2 + [_ok_completion()]

    with patch("litellm.completion", side_effect=side_effect) as completion:
        result = await rt.Flow(name="Model retry", entry_point=agent).ainvoke("Hi")

    assert result.text == "ok"
    assert completion.call_count == 3


@pytest.mark.parametrize(
    "error_type, node_error",
    [(litellm.RateLimitError, LLMRateLimitError), (litellm.Timeout, LLMTimeoutError)],
)
async def test_exhausted_model_middleware_retry_keeps_the_error_type(
    error_type, node_error
):
    agent = _openai_agent(model_middleware=[_no_sleep_retry()])

    with patch(
        "litellm.completion", side_effect=_provider_failure(error_type)
    ) as completion:
        with pytest.raises(node_error) as exc:
            await rt.Flow(name="Model retry", entry_point=agent).ainvoke("Hi")

    assert type(exc.value) is node_error
    assert exc.value.retry_exhausted
    assert completion.call_count == 3


async def test_model_and_node_retry_on_a_real_provider_do_not_multiply():
    agent = _openai_agent(
        middleware=[_no_sleep_retry()], model_middleware=[_no_sleep_retry()]
    )

    with patch(
        "litellm.completion", side_effect=_provider_failure(litellm.RateLimitError)
    ) as completion:
        with pytest.raises(LLMRateLimitError):
            await rt.Flow(name="Stacked retries", entry_point=agent).ainvoke("Hi")

    assert completion.call_count == 3
