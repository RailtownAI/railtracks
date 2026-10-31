"""Unit tests for the prebuilt Retry middleware: `rt.prebuilt.middleware.Retry`.

Retry is slot-agnostic — it only re-invokes `call` — so the tests wire it
directly via `.wrap(fake_call)` and through decision nodes.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import litellm
import pytest
import railtracks as rt
from railtracks.decisions import (
    DecisionProviderRateLimitError,
    DecisionProviderRefusalError,
    DecisionProviderTimeoutError,
)
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
    cause = exc.value.__cause__
    provider_type = (
        DecisionProviderTimeoutError
        if node_error is DecisionTimeoutError
        else DecisionProviderRateLimitError
    )
    assert type(cause) is provider_type
    assert type(cause.__cause__) is provider_error
    history = exc.value.__context__
    assert isinstance(history, RetryError)
    assert len(history.exception_list) == 3
    assert all(type(error) is node_error for error in history.exception_list)
    last = history.exception_list[-1]
    assert exc.value is not last
    assert last.__cause__ is cause
    assert last.notes == []
    assert exc.value.notes == ["Gave up after 3 attempts."]
    assert exc.value.retry_exhausted
    assert exc.value.retry_errors == tuple(history.exception_list)
    assert "Gave up after 3 attempts." in str(exc.value)
    seen = set()
    error = exc.value
    while error is not None:
        assert id(error) not in seen, f"Cause cycle at {error!r}"
        seen.add(id(error))
        error = error.__cause__
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


async def test_function_node_exhaustion_preserves_decision_error(decision_model):
    model, provider_call = decision_model
    provider_call.side_effect = litellm.Timeout(
        message="timed out", llm_provider="typesafe", model="jev-latest"
    )
    decision = rt.decision_node(model=model, schema=Triage)
    forward = _forwarding_node(decision, _no_sleep_retry(retry_on=(Exception,)))

    with pytest.raises(DecisionTimeoutError) as exc:
        await rt.Flow(name="Retry function", entry_point=forward).ainvoke("Help!")

    assert provider_call.await_count == 3
    assert exc.value.retry_exhausted
    assert len(exc.value.retry_errors) == 3
    assert all(
        isinstance(error, DecisionTimeoutError) for error in exc.value.retry_errors
    )


def _forwarding_node(decision, retry):
    @rt.function_node(middleware=[retry])
    async def forward(state: str) -> rt.decisions.DecisionResponse:
        """Ask a decision node about the supplied text.

        Args:
            state: The text to judge.

        Returns:
            The decision node's answers.
        """
        return await rt.call(decision, state)

    return forward


@pytest.mark.parametrize("provider_error", [litellm.Timeout, litellm.RateLimitError])
@pytest.mark.parametrize("outer_layer", ["model", "function", "model_in_function"])
@pytest.mark.parametrize("decision_retry", [False, True])
@pytest.mark.parametrize("broad_retry_on", [False, True])
async def test_stacked_retry_layers_stop_after_inner_exhaustion(
    decision_model, provider_error, outer_layer, decision_retry, broad_retry_on
):
    model, provider_call = decision_model
    provider_call.side_effect = provider_error(
        message="transient", llm_provider="typesafe", model="jev-latest"
    )
    if outer_layer != "function":
        model.retry_approach = FixedRetry(max_tries=3, delay=0.0)
    retry_options = {"retry_on": (Exception,)} if broad_retry_on else {}
    decision = rt.decision_node(
        model=model,
        schema=Triage,
        middleware=[_no_sleep_retry(**retry_options)] if decision_retry else None,
    )
    entry = (
        _forwarding_node(decision, _no_sleep_retry(**retry_options))
        if outer_layer != "model"
        else decision
    )

    with pytest.raises(DecisionModelError) as exc:
        await rt.Flow(name="Stacked retries", entry_point=entry).ainvoke("Help!")

    assert provider_call.await_count == 3
    assert exc.value.retry_exhausted
    assert exc.value.notes == ["Gave up after 3 attempts."]
    assert len(exc.value.retry_errors) == 3


async def test_two_retries_on_one_decision_node_do_not_retry_retry_error(
    decision_model,
):
    model, provider_call = decision_model
    provider_call.side_effect = litellm.Timeout(
        message="timed out", llm_provider="typesafe", model="jev-latest"
    )
    node = rt.decision_node(
        model=model,
        schema=Triage,
        middleware=[_no_sleep_retry(), _no_sleep_retry()],
    )

    with pytest.raises(DecisionTimeoutError):
        await rt.Flow(name="Two retries", entry_point=node).ainvoke("Help!")

    assert provider_call.await_count == 3


async def test_custom_retry_preserves_refusal_details_and_notes(decision_model):
    model, provider_call = decision_model
    provider_call.side_effect = DecisionProviderRefusalError(
        "declined", refused=["is_urgent"], answers={}, notes=["original note"]
    )
    node = rt.decision_node(
        model=model, schema=Triage, middleware=[_no_sleep_retry(retry_on=(Exception,))]
    )

    with pytest.raises(DecisionRefusalError) as exc:
        await rt.Flow(name="Retry refusal", entry_point=node).ainvoke("Help!")

    history = exc.value.__context__
    assert isinstance(history, RetryError)
    last = history.exception_list[-1]
    assert exc.value is not last
    assert exc.value.refused == last.refused == ["is_urgent"]
    assert exc.value.refused is not last.refused
    assert exc.value.answers == last.answers == {}
    assert exc.value.answers is not last.answers
    assert exc.value.notes == ["original note", "Gave up after 3 attempts."]
    assert last.notes == ["original note"]
    assert exc.value.__cause__ is last.__cause__


async def test_fallback_outside_retry_sees_decision_error(decision_model):
    model, provider_call = decision_model
    provider_call.return_value = respond()
    default = await model.aask("default", Triage)
    provider_call.reset_mock()
    provider_call.side_effect = litellm.Timeout(
        message="timed out", llm_provider="typesafe", model="jev-latest"
    )

    @rt.wrap_node
    async def fallback(call, state):
        try:
            return await call(state)
        except DecisionModelError:
            return default

    node = rt.decision_node(
        model=model, schema=Triage, middleware=[fallback, _no_sleep_retry()]
    )

    result = await rt.Flow(name="Fallback", entry_point=node).ainvoke("Help!")

    assert result is default
    assert provider_call.await_count == 3


async def test_exhaustion_preserves_custom_constructor_attributes_and_python_notes():
    class CustomTimeoutError(DecisionTimeoutError):
        __slots__ = ("request_id",)

        def __init__(self, request_id: str):
            super().__init__("timed out", notes=["original note"], fatal=True)
            self.request_id = request_id
            self.extra = "custom attribute"

    last = CustomTimeoutError("request-123")
    last.add_note("Python exception note")
    provider_error = DecisionProviderTimeoutError("provider timed out")
    last.__cause__ = provider_error
    call = AsyncMock(side_effect=last)

    with pytest.raises(CustomTimeoutError) as exc:
        await _no_sleep_retry(max_tries=1).wrap(call)()

    assert exc.value is not last
    assert exc.value.request_id == "request-123"
    assert exc.value.extra == "custom attribute"
    assert exc.value.fatal
    assert exc.value.__notes__ == last.__notes__ == ["Python exception note"]
    assert exc.value.__notes__ is not last.__notes__
    assert exc.value.notes == ["original note", "Gave up after 1 attempts."]
    assert last.notes == ["original note"]
    assert exc.value.__cause__ is provider_error
    assert exc.value.retry_errors == (last,)
    assert exc.value.retry_exhausted
    assert not last.retry_exhausted
