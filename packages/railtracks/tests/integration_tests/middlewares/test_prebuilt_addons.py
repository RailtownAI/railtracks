"""Integration tests for the prebuilt add-ons (`rt.prebuilt.middleware.Retry`,
`rt.prebuilt.middleware.ContextInjection`) wired through real nodes.

ContextInjection's session/config gating is covered in
test_middleware_integration.py (TestContextInjection) and unit_tests/prompt;
here the focus is Retry in both slots — the acceptance criterion of #1273.
"""

from __future__ import annotations

import litellm
import pytest
import railtracks as rt
from railtracks.built_nodes.llm.response import StringResponse
from railtracks.llm.retries import FixedRetry


def _rate_limit_error() -> litellm.exceptions.RateLimitError:
    return litellm.exceptions.RateLimitError(
        message="rate limited", llm_provider="openai", model="gpt-4o"
    )


def _fast_retry(max_tries: int = 3, **kwargs) -> rt.prebuilt.middleware.Retry:
    return rt.prebuilt.middleware.Retry(
        approach=FixedRetry(max_tries=max_tries, delay=0.0), **kwargs
    )


@pytest.mark.asyncio
async def test_retry_in_model_middleware_recovers_from_transient_llm_error(mock_llm):
    llm = mock_llm(custom_response="recovered", errors=[_rate_limit_error])

    agent = rt.agent_node(
        name="retry-model",
        llm=llm,
        model_middleware=[_fast_retry()],
    )

    with rt.Session():
        out = await rt.call(agent, user_input="hi")

    assert isinstance(out, StringResponse)
    assert "recovered" in out.text


@pytest.mark.asyncio
async def test_retry_in_node_middleware_retries_a_flaky_function():
    calls = {"n": 0}

    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise ValueError("transient")
        return "done"

    node = rt.function_node(
        flaky,
        middleware=[_fast_retry(retry_on=(Exception,))],
    )

    with rt.Session():
        out = await rt.call(node)

    assert out == "done"
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_retry_exhaustion_surfaces_after_max_tries(mock_llm):
    llm = mock_llm(
        custom_response="never reached",
        errors=[_rate_limit_error, _rate_limit_error, _rate_limit_error],
    )

    agent = rt.agent_node(
        name="retry-exhausted",
        llm=llm,
        model_middleware=[_fast_retry(max_tries=2)],
    )

    with rt.Session():
        with pytest.raises(Exception):
            await rt.call(agent, user_input="hi")
