"""Unit tests for railtracks.llm.retries — no I/O, all sleeps are mocked."""
from unittest.mock import AsyncMock, call, patch

import litellm
import pytest

from railtracks.llm._exceptions import RetryError
from railtracks.llm.retries import ExponentialRetry, FixedRetry, LinearRetry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rate_limit_error() -> litellm.exceptions.RateLimitError:
    return litellm.exceptions.RateLimitError(
        message="rate limited", llm_provider="openai", model="gpt-4"
    )


def _timeout_error() -> litellm.exceptions.Timeout:
    return litellm.exceptions.Timeout(
        message="timed out", model="gpt-4", llm_provider="openai"
    )


def _internal_server_error() -> litellm.exceptions.InternalServerError:
    return litellm.exceptions.InternalServerError(
        message="server error", llm_provider="openai", model="gpt-4"
    )


def _bad_request_error() -> litellm.exceptions.BadRequestError:
    return litellm.exceptions.BadRequestError(
        message="bad request", model="gpt-4", llm_provider="openai"
    )


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------

class TestExponentialRetryValidation:
    def test_max_tries_below_1_raises(self):
        with pytest.raises(ValueError, match="max_tries"):
            ExponentialRetry(max_tries=0)

    def test_max_tries_above_20_raises(self):
        with pytest.raises(ValueError, match="max_tries"):
            ExponentialRetry(max_tries=21)

    def test_base_below_1_raises(self):
        with pytest.raises(ValueError, match="base"):
            ExponentialRetry(max_tries=3, base=0.5)

    def test_valid_instantiation(self):
        retry = ExponentialRetry(max_tries=3, base=2.0, jitter=False)
        assert retry._max_tries == 3
        assert retry._base == 2.0


class TestLinearRetryValidation:
    def test_max_tries_below_1_raises(self):
        with pytest.raises(ValueError, match="max_tries"):
            LinearRetry(max_tries=0)

    def test_max_tries_above_100_raises(self):
        with pytest.raises(ValueError, match="max_tries"):
            LinearRetry(max_tries=101)

    def test_negative_step_raises(self):
        with pytest.raises(ValueError, match="step"):
            LinearRetry(max_tries=3, step=-1.0)

    def test_zero_step_is_valid(self):
        retry = LinearRetry(max_tries=3, step=0.0)
        assert retry._step == 0.0


class TestFixedRetryValidation:
    def test_max_tries_below_1_raises(self):
        with pytest.raises(ValueError, match="max_tries"):
            FixedRetry(max_tries=0)

    def test_max_tries_above_100_raises(self):
        with pytest.raises(ValueError, match="max_tries"):
            FixedRetry(max_tries=101)

    def test_negative_delay_raises(self):
        with pytest.raises(ValueError, match="delay"):
            FixedRetry(max_tries=3, delay=-1.0)

    def test_zero_delay_is_valid(self):
        retry = FixedRetry(max_tries=3, delay=0.0)
        assert retry._delay == 0.0


# ---------------------------------------------------------------------------
# _compute_delay
# ---------------------------------------------------------------------------

class TestExponentialDelay:
    def test_no_jitter_doubles_each_attempt(self):
        retry = ExponentialRetry(max_tries=5, base=2.0, jitter=False)
        assert retry._compute_delay(0) == 1.0
        assert retry._compute_delay(1) == 2.0
        assert retry._compute_delay(2) == 4.0
        assert retry._compute_delay(3) == 8.0

    def test_jitter_within_range(self):
        retry = ExponentialRetry(max_tries=5, base=2.0, jitter=True)
        for attempt in range(4):
            delay = retry._compute_delay(attempt)
            assert 0.0 <= delay <= 2.0**attempt


class TestLinearDelay:
    def test_no_jitter_increments_by_step(self):
        retry = LinearRetry(max_tries=5, step=2.0, jitter=False)
        assert retry._compute_delay(0) == 2.0
        assert retry._compute_delay(1) == 4.0
        assert retry._compute_delay(2) == 6.0

    def test_jitter_within_range(self):
        retry = LinearRetry(max_tries=5, step=3.0, jitter=True)
        for attempt in range(4):
            delay = retry._compute_delay(attempt)
            assert 0.0 <= delay <= 3.0 * (attempt + 1)


class TestFixedDelay:
    def test_always_returns_same_delay(self):
        retry = FixedRetry(max_tries=5, delay=5.0)
        for attempt in range(4):
            assert retry._compute_delay(attempt) == 5.0

    def test_zero_delay(self):
        retry = FixedRetry(max_tries=3, delay=0.0)
        assert retry._compute_delay(0) == 0.0


# ---------------------------------------------------------------------------
# approach_name
# ---------------------------------------------------------------------------

def test_approach_names():
    assert ExponentialRetry.approach_name() == "exponential"
    assert LinearRetry.approach_name() == "linear"
    assert FixedRetry.approach_name() == "fixed"


# ---------------------------------------------------------------------------
# call_with_retry
# ---------------------------------------------------------------------------

class TestCallWithRetry:
    def test_succeeds_on_first_call(self):
        retry = ExponentialRetry(max_tries=3, jitter=False)
        result = retry.call_with_retry(lambda: "ok")
        assert result == "ok"

    def test_retries_then_succeeds(self):
        state = {"n": 0}

        def flaky():
            state["n"] += 1
            if state["n"] < 3:
                raise _rate_limit_error()
            return "ok"

        with patch("railtracks.llm.retries.base.time.sleep"):
            retry = ExponentialRetry(max_tries=3, jitter=False)
            result = retry.call_with_retry(flaky)

        assert result == "ok"
        assert state["n"] == 3

    def test_exhausts_retries_raises_retry_error(self):
        with patch("railtracks.llm.retries.base.time.sleep"):
            retry = ExponentialRetry(max_tries=3, jitter=False)
            with pytest.raises(RetryError) as exc_info:
                retry.call_with_retry(lambda: (_ for _ in ()).throw(_rate_limit_error()))

        assert len(exc_info.value.exception_list) == 3

    def test_non_retryable_exception_bubbles_up_immediately(self):
        state = {"n": 0}

        def raises_bad_request():
            state["n"] += 1
            raise _bad_request_error()

        with patch("railtracks.llm.retries.base.time.sleep") as mock_sleep:
            retry = ExponentialRetry(max_tries=5, jitter=False)
            with pytest.raises(litellm.exceptions.BadRequestError):
                retry.call_with_retry(raises_bad_request)

        assert state["n"] == 1
        mock_sleep.assert_not_called()

    def test_uses_computed_delay_between_retries(self):
        state = {"n": 0}

        def flaky():
            state["n"] += 1
            if state["n"] < 3:
                raise _rate_limit_error()
            return "ok"

        with patch("railtracks.llm.retries.base.time.sleep") as mock_sleep:
            retry = ExponentialRetry(max_tries=3, base=2.0, jitter=False)
            retry.call_with_retry(flaky)

        assert mock_sleep.call_args_list == [call(1.0), call(2.0)]

    @pytest.mark.parametrize("error_factory", [
        _rate_limit_error,
        _timeout_error,
        _internal_server_error,
    ], ids=["RateLimitError", "Timeout", "InternalServerError"])
    def test_all_retryable_exception_types_are_retried(self, error_factory):
        state = {"n": 0}

        def flaky():
            state["n"] += 1
            if state["n"] < 2:
                raise error_factory()
            return "ok"

        with patch("railtracks.llm.retries.base.time.sleep"):
            retry = FixedRetry(max_tries=3, delay=0.0)
            result = retry.call_with_retry(flaky)

        assert result == "ok"

    def test_retry_error_contains_all_exceptions(self):
        errors = []

        def always_fails():
            e = _rate_limit_error()
            errors.append(e)
            raise e

        with patch("railtracks.llm.retries.base.time.sleep"):
            retry = ExponentialRetry(max_tries=3, jitter=False)
            with pytest.raises(RetryError) as exc_info:
                retry.call_with_retry(always_fails)

        assert exc_info.value.exception_list == errors


# ---------------------------------------------------------------------------
# acall_with_retry
# ---------------------------------------------------------------------------

class TestACallWithRetry:
    @pytest.mark.asyncio
    async def test_succeeds_on_first_call(self):
        async def completion():
            return "ok"

        retry = ExponentialRetry(max_tries=3, jitter=False)
        result = await retry.acall_with_retry(completion)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_retries_then_succeeds(self):
        state = {"n": 0}

        async def flaky():
            state["n"] += 1
            if state["n"] < 3:
                raise _rate_limit_error()
            return "ok"

        with patch("railtracks.llm.retries.base.asyncio.sleep", new_callable=AsyncMock):
            retry = ExponentialRetry(max_tries=3, jitter=False)
            result = await retry.acall_with_retry(flaky)

        assert result == "ok"
        assert state["n"] == 3

    @pytest.mark.asyncio
    async def test_exhausts_retries_raises_retry_error(self):
        async def always_fails():
            raise _rate_limit_error()

        with patch("railtracks.llm.retries.base.asyncio.sleep", new_callable=AsyncMock):
            retry = ExponentialRetry(max_tries=3, jitter=False)
            with pytest.raises(RetryError) as exc_info:
                await retry.acall_with_retry(always_fails)

        assert len(exc_info.value.exception_list) == 3

    @pytest.mark.asyncio
    async def test_non_retryable_exception_bubbles_up_immediately(self):
        state = {"n": 0}

        async def raises_bad_request():
            state["n"] += 1
            raise _bad_request_error()

        with patch("railtracks.llm.retries.base.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            retry = ExponentialRetry(max_tries=5, jitter=False)
            with pytest.raises(litellm.exceptions.BadRequestError):
                await retry.acall_with_retry(raises_bad_request)

        assert state["n"] == 1
        mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_uses_computed_delay_between_retries(self):
        state = {"n": 0}

        async def flaky():
            state["n"] += 1
            if state["n"] < 3:
                raise _rate_limit_error()
            return "ok"

        with patch("railtracks.llm.retries.base.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            retry = LinearRetry(max_tries=3, step=5.0, jitter=False)
            await retry.acall_with_retry(flaky)

        assert mock_sleep.call_args_list == [call(5.0), call(10.0)]
