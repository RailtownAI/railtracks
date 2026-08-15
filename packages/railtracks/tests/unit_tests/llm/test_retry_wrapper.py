"""Tests for retry_approach wiring inside LiteLLMWrapper via real provider classes."""
from unittest.mock import patch

import litellm
import pytest
from litellm.utils import ModelResponse
from railtracks.llm._exceptions import RetryError
from railtracks.llm.models.api_providers import AnthropicLLM, OpenAILLM
from railtracks.llm.retries import ExponentialRetry, FixedRetry


def _ok_response() -> ModelResponse:
    return ModelResponse(
        choices=[{"message": {"content": "hello", "role": "assistant"}, "finish_reason": "stop"}]
    )


def _rate_limit_error() -> litellm.exceptions.RateLimitError:
    return litellm.exceptions.RateLimitError(
        message="rate limited", llm_provider="anthropic", model="claude-haiku-4-5-20251001"
    )


# ---------------------------------------------------------------------------
# Sync _invoke retry tests — AnthropicLLM
# ---------------------------------------------------------------------------

class TestSyncRetryInWrapper:
    def test_no_retry_approach_passes_through(self, message_history):
        llm = AnthropicLLM("claude-haiku-4-5-20251001")
        with patch.object(litellm, "completion", return_value=_ok_response()) as mock_completion:
            llm.chat(message_history)
        mock_completion.assert_called_once()

    def test_retries_on_rate_limit_error(self, message_history):
        call_count = {"n": 0}

        def _side_effect(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise _rate_limit_error()
            return _ok_response()

        llm = AnthropicLLM(
            "claude-haiku-4-5-20251001",
            retry_approach=FixedRetry(max_tries=5, delay=0.0),
        )
        with patch.object(litellm, "completion", side_effect=_side_effect):
            with patch("railtracks.llm.retries.base.time.sleep"):
                response = llm.chat(message_history)

        assert call_count["n"] == 3
        assert response.message.content == "hello"

    def test_raises_retry_error_after_max_tries(self, message_history):
        llm = AnthropicLLM(
            "claude-haiku-4-5-20251001",
            retry_approach=FixedRetry(max_tries=3, delay=0.0),
        )
        with patch.object(litellm, "completion", side_effect=_rate_limit_error()):
            with patch("railtracks.llm.retries.base.time.sleep"):
                with pytest.raises(RetryError):
                    llm.chat(message_history)

    def test_non_retryable_error_propagates_without_retry(self, message_history):
        call_count = {"n": 0}

        def _bad_request(*args, **kwargs):
            call_count["n"] += 1
            raise litellm.exceptions.BadRequestError(
                message="bad", model="claude-haiku-4-5-20251001", llm_provider="anthropic"
            )

        llm = AnthropicLLM(
            "claude-haiku-4-5-20251001",
            retry_approach=FixedRetry(max_tries=5, delay=0.0),
        )
        with patch.object(litellm, "completion", side_effect=_bad_request):
            with patch("railtracks.llm.retries.base.time.sleep"):
                with pytest.raises(litellm.exceptions.BadRequestError):
                    llm.chat(message_history)

        assert call_count["n"] == 1

    def test_correct_exponential_sleep_durations(self, message_history):
        call_count = {"n": 0}

        def _flaky(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise _rate_limit_error()
            return _ok_response()

        llm = AnthropicLLM(
            "claude-haiku-4-5-20251001",
            retry_approach=ExponentialRetry(max_tries=5, base=2.0, jitter=False),
        )
        with patch.object(litellm, "completion", side_effect=_flaky):
            with patch("railtracks.llm.retries.base.time.sleep") as mock_sleep:
                llm.chat(message_history)

        sleep_calls = [c.args[0] for c in mock_sleep.call_args_list]
        assert sleep_calls == [1.0, 2.0]  # 2^0 then 2^1


# ---------------------------------------------------------------------------
# Async surface retry tests — OpenAILLM
#
# `achat` runs the synchronous `litellm.completion` (with the sync retry loop) on a worker
# thread, so retries are driven by `completion` + `time.sleep`, not the async path.
# ---------------------------------------------------------------------------

class TestAsyncRetryInWrapper:
    @pytest.mark.asyncio
    async def test_retries_on_rate_limit_error(self, message_history):
        call_count = {"n": 0}

        def _side_effect(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise litellm.exceptions.RateLimitError(
                    message="rate limited", llm_provider="openai", model="gpt-4o-mini"
                )
            return _ok_response()

        llm = OpenAILLM(
            "gpt-4o-mini",
            retry_approach=FixedRetry(max_tries=5, delay=0.0),
        )
        with patch.object(litellm, "completion", side_effect=_side_effect):
            with patch("railtracks.llm.retries.base.time.sleep"):
                response = await llm.achat(message_history)

        assert call_count["n"] == 3
        assert response.message.content == "hello"

    @pytest.mark.asyncio
    async def test_raises_retry_error_after_max_tries(self, message_history):
        def _always_fails(*args, **kwargs):
            raise litellm.exceptions.RateLimitError(
                message="rate limited", llm_provider="openai", model="gpt-4o-mini"
            )

        llm = OpenAILLM(
            "gpt-4o-mini",
            retry_approach=FixedRetry(max_tries=3, delay=0.0),
        )
        with patch.object(litellm, "completion", side_effect=_always_fails):
            with patch("railtracks.llm.retries.base.time.sleep"):
                with pytest.raises(RetryError):
                    await llm.achat(message_history)

    @pytest.mark.asyncio
    async def test_non_retryable_error_propagates_without_retry(self, message_history):
        call_count = {"n": 0}

        def _bad_request(*args, **kwargs):
            call_count["n"] += 1
            raise litellm.exceptions.BadRequestError(
                message="bad", model="gpt-4o-mini", llm_provider="openai"
            )

        llm = OpenAILLM(
            "gpt-4o-mini",
            retry_approach=FixedRetry(max_tries=5, delay=0.0),
        )
        with patch.object(litellm, "completion", side_effect=_bad_request):
            with patch("railtracks.llm.retries.base.time.sleep"):
                with pytest.raises(litellm.exceptions.BadRequestError):
                    await llm.achat(message_history)

        assert call_count["n"] == 1
