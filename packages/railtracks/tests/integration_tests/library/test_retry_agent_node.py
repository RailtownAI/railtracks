"""Integration tests: retry_approach wired through agent_node → rt.call()."""
from unittest.mock import patch

import litellm
import pytest
from litellm.utils import ModelResponse

import railtracks as rt
from railtracks.exceptions import LLMError
from railtracks.llm.models.api_providers import AnthropicLLM, OpenAILLM
from railtracks.llm.retries import ExponentialRetry, FixedRetry


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _ok_response(text: str = "hello") -> ModelResponse:
    return ModelResponse(
        choices=[{"message": {"content": text, "role": "assistant"}, "finish_reason": "stop"}]
    )


def _rate_limit_error() -> litellm.exceptions.RateLimitError:
    return litellm.exceptions.RateLimitError(
        message="rate limited", llm_provider="anthropic", model="claude-haiku-4-5-20251001"
    )


# ---------------------------------------------------------------------------
# Retry succeeds — agent_node returns a response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_agent_node_succeeds_after_retries():
    """Agent node returns a valid response when litellm fails twice then succeeds."""
    call_count = {"n": 0}

    def _flaky(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise _rate_limit_error()
        return _ok_response("final answer")

    llm = AnthropicLLM(
        "claude-haiku-4-5-20251001",
        retry_approach=FixedRetry(max_tries=5, delay=0.0),
    )
    agent = rt.agent_node(
        name="RetryAgent",
        system_message="You are a helpful assistant.",
        llm=llm,
    )

    with patch.object(litellm, "completion", side_effect=_flaky):
        with patch("railtracks.llm.retries.base.time.sleep"):
            response = await rt.call(agent, user_input="hello")

    assert call_count["n"] == 3
    assert response.text == "final answer"


@pytest.mark.asyncio
async def test_agent_node_succeeds_on_first_call_with_retry_approach():
    """Retry approach does not interfere when litellm succeeds immediately."""
    call_count = {"n": 0}

    def _ok(*args, **kwargs):
        call_count["n"] += 1
        return _ok_response("immediate success")

    llm = AnthropicLLM(
        "claude-haiku-4-5-20251001",
        retry_approach=ExponentialRetry(max_tries=3, jitter=False),
    )
    agent = rt.agent_node(
        name="RetryAgent",
        system_message="You are a helpful assistant.",
        llm=llm,
    )

    with patch.object(litellm, "completion", side_effect=_ok):
        response = await rt.call(agent, user_input="hello")

    assert call_count["n"] == 1
    assert response.text == "immediate success"


# ---------------------------------------------------------------------------
# Retry exhausted — exception propagates out of rt.call()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_agent_node_raises_when_exhausted():
    """rt.call() raises LLMError (wrapping RetryError) when all retries fail.

    The agent layer normalises all LLM exceptions to LLMError before surfacing
    them to the caller.
    """
    llm = AnthropicLLM(
        "claude-haiku-4-5-20251001",
        retry_approach=FixedRetry(max_tries=3, delay=0.0),
    )
    agent = rt.agent_node(
        name="RetryAgent",
        system_message="You are a helpful assistant.",
        llm=llm,
    )

    with patch.object(litellm, "completion", side_effect=_rate_limit_error()):
        with patch("railtracks.llm.retries.base.time.sleep"):
            with pytest.raises(LLMError):
                await rt.call(agent, user_input="hello")


# ---------------------------------------------------------------------------
# No retry approach — original behaviour is unchanged
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_agent_node_without_retry_approach_raises_immediately():
    """Without retry_approach the agent does not retry — litellm is called exactly once."""
    call_count = {"n": 0}

    def _rate_limit(*args, **kwargs):
        call_count["n"] += 1
        raise _rate_limit_error()

    llm = AnthropicLLM("claude-haiku-4-5-20251001")  # no retry_approach
    agent = rt.agent_node(
        name="NoRetryAgent",
        system_message="You are a helpful assistant.",
        llm=llm,
    )

    with patch.object(litellm, "completion", side_effect=_rate_limit):
        with pytest.raises(LLMError):
            await rt.call(agent, user_input="hello")

    assert call_count["n"] == 1


# ---------------------------------------------------------------------------
# Exponential backoff — verify sleep durations observed by agent_node path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_agent_node_exponential_sleep_durations():
    """Verify the correct exponential delays are passed to time.sleep."""
    call_count = {"n": 0}

    def _flaky(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] < 4:
            raise _rate_limit_error()
        return _ok_response()

    llm = AnthropicLLM(
        "claude-haiku-4-5-20251001",
        retry_approach=ExponentialRetry(max_tries=5, base=2.0, jitter=False),
    )
    agent = rt.agent_node(
        name="RetryAgent",
        system_message="You are a helpful assistant.",
        llm=llm,
    )

    with patch.object(litellm, "completion", side_effect=_flaky):
        with patch("railtracks.llm.retries.base.time.sleep") as mock_sleep:
            await rt.call(agent, user_input="hello")

    sleep_calls = [c.args[0] for c in mock_sleep.call_args_list]
    assert sleep_calls == [1.0, 2.0, 4.0]  # 2^0, 2^1, 2^2


# ---------------------------------------------------------------------------
# Cross-provider — OpenAILLM also honours retry_approach
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_openai_agent_node_retries():
    """retry_approach works with OpenAILLM in the same way."""
    call_count = {"n": 0}

    def _flaky(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] < 2:
            raise litellm.exceptions.RateLimitError(
                message="rate limited", llm_provider="openai", model="gpt-4o-mini"
            )
        return _ok_response("openai response")

    llm = OpenAILLM(
        "gpt-4o-mini",
        retry_approach=FixedRetry(max_tries=3, delay=0.0),
    )
    agent = rt.agent_node(
        name="OpenAIRetryAgent",
        system_message="You are a helpful assistant.",
        llm=llm,
    )

    with patch.object(litellm, "completion", side_effect=_flaky):
        with patch("railtracks.llm.retries.base.time.sleep"):
            response = await rt.call(agent, user_input="hello")

    assert call_count["n"] == 2
    assert response.text == "openai response"
