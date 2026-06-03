"""Integration tests: retry_approach wired through agent_node → rt.call()."""
from unittest.mock import patch

import litellm
import pytest

import railtracks as rt
from railtracks.exceptions import LLMError
from railtracks.llm.retries import ExponentialRetry, FixedRetry


def _rate_limit_error():
    return litellm.exceptions.RateLimitError(
        message="rate limited", llm_provider="mock", model="MockLLM"
    )


# ---------------------------------------------------------------------------
# Retry succeeds — agent_node returns a response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_agent_node_succeeds_after_retries(mock_llm):
    """Agent node returns a valid response when the LLM fails twice then succeeds."""
    llm = mock_llm(
        custom_response="final answer",
        errors=[_rate_limit_error, _rate_limit_error],
        retry_approach=FixedRetry(max_tries=5, delay=0.0),
    )
    agent = rt.agent_node(
        name="RetryAgent",
        system_message="You are a helpful assistant.",
        llm=llm,
    )

    with patch("railtracks.llm.retries.base.time.sleep"):
        response = await rt.call(agent, user_input="hello")

    assert response.text == "final answer"


@pytest.mark.asyncio
async def test_agent_node_succeeds_on_first_call_with_retry_approach(mock_llm):
    """Retry approach does not interfere when the LLM succeeds immediately."""
    llm = mock_llm(
        custom_response="immediate success",
        retry_approach=ExponentialRetry(max_tries=3, jitter=False),
    )
    agent = rt.agent_node(
        name="RetryAgent",
        system_message="You are a helpful assistant.",
        llm=llm,
    )

    response = await rt.call(agent, user_input="hello")
    assert response.text == "immediate success"


# ---------------------------------------------------------------------------
# Retry exhausted — exception propagates out of rt.call()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_agent_node_raises_when_exhausted(mock_llm):
    """rt.call() raises LLMError (wrapping RetryError) when all retries fail.

    The agent layer normalises all LLM exceptions to LLMError before surfacing
    them to the caller.
    """
    llm = mock_llm(
        errors=[_rate_limit_error, _rate_limit_error, _rate_limit_error],
        retry_approach=FixedRetry(max_tries=3, delay=0.0),
    )
    agent = rt.agent_node(
        name="RetryAgent",
        system_message="You are a helpful assistant.",
        llm=llm,
    )

    with patch("railtracks.llm.retries.base.time.sleep"):
        with pytest.raises(LLMError):
            await rt.call(agent, user_input="hello")


# ---------------------------------------------------------------------------
# No retry approach — original behaviour is unchanged
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_agent_node_without_retry_approach_raises_immediately(mock_llm):
    """Without retry_approach the agent does not retry — the error surfaces as LLMError."""
    llm = mock_llm(errors=[_rate_limit_error])
    agent = rt.agent_node(
        name="NoRetryAgent",
        system_message="You are a helpful assistant.",
        llm=llm,
    )

    with pytest.raises(LLMError):
        await rt.call(agent, user_input="hello")


# ---------------------------------------------------------------------------
# Exponential backoff — verify sleep durations observed by agent_node path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_agent_node_exponential_sleep_durations(mock_llm):
    """Verify the correct exponential delays are passed to time.sleep."""
    llm = mock_llm(
        errors=[_rate_limit_error, _rate_limit_error, _rate_limit_error],
        retry_approach=ExponentialRetry(max_tries=5, base=2.0, jitter=False),
    )
    agent = rt.agent_node(
        name="RetryAgent",
        system_message="You are a helpful assistant.",
        llm=llm,
    )

    with patch("railtracks.llm.retries.base.time.sleep") as mock_sleep:
        await rt.call(agent, user_input="hello")

    sleep_calls = [c.args[0] for c in mock_sleep.call_args_list]
    assert sleep_calls == [1.0, 2.0, 4.0]  # 2^0, 2^1, 2^2
