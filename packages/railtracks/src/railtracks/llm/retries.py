import asyncio
import random
import time
import warnings
from abc import ABC, abstractmethod
from typing import Awaitable, Callable, TypeVar

import litellm

from ._exceptions import RetryError

_TResult = TypeVar("_TResult")

_RETRYABLE_EXCEPTIONS = (
    litellm.exceptions.RateLimitError,
    litellm.exceptions.Timeout,
    litellm.exceptions.InternalServerError,
    litellm.exceptions.ServiceUnavailableError,
    litellm.exceptions.APIConnectionError,
)

_MAX_RECOMONDED_RETRY_TIME_EXPONETIAL = (
    1000  # 1000 seconds feels like a reasonable bound
)
_MAX_RETRY_TIMES_EXPONETIAL = 20
_MAX_RETRY_TIMES_FIXED = 100
_MAX_RETRY_TIMES_LINEAR = 100


def _extract_retry_after(e: Exception) -> float | None:
    """Return Retry-After header value in seconds, or None if absent.

    litellm.exceptions.Timeout carries headers directly on the exception; all other
    retryable exceptions carry them on e.response.
    """
    if isinstance(e, litellm.exceptions.Timeout):
        headers = getattr(e, "headers", None)
    else:
        response = getattr(e, "response", None)
        headers = getattr(response, "headers", None) if response else None

    if headers is None:
        return None

    value = headers.get("Retry-After")
    try:
        return float(value) if value is not None else None
    except (ValueError, TypeError):
        return None


class RetryApproach(ABC):
    def __init__(self, max_tries: int, use_retry_recommendation: bool) -> None:
        if max_tries < 1:
            raise ValueError("max_tries must be >= 1")
        self._max_tries = max_tries
        self._use_retry_recommendation = use_retry_recommendation

    @classmethod
    @abstractmethod
    def approach_name(cls) -> str:
        pass

    @abstractmethod
    def _compute_delay(self, attempt: int) -> float:
        """Seconds to wait before retrying after `attempt` (0-indexed)."""
        pass

    def call_with_retry(self, completion: Callable[[], _TResult]) -> _TResult:
        exceptions: list[Exception] = []

        for attempt in range(self._max_tries):
            try:
                return completion()
            # we only want to retry on exceptions which make sense to retry on.
            except _RETRYABLE_EXCEPTIONS as e:
                exceptions.append(e)
                if attempt == self._max_tries - 1:
                    raise RetryError(
                        self.approach_name(),
                        "Max retries exceeded",
                        ["Examine exceptions to determine the root cause."],
                        exceptions,
                    ) from e

                if self._use_retry_recommendation:
                    delay = _extract_retry_after(e)
                else:
                    delay = None

                if delay is not None:
                    time.sleep(delay)
                else:
                    time.sleep(self._compute_delay(attempt))

        assert False, "Unreachable code"

    async def acall_with_retry(
        self, completion: Callable[[], Awaitable[_TResult]]
    ) -> _TResult:
        exceptions: list[Exception] = []

        for attempt in range(self._max_tries):
            try:
                return await completion()
            except _RETRYABLE_EXCEPTIONS as e:
                exceptions.append(e)
                if attempt == self._max_tries - 1:
                    raise RetryError(
                        self.approach_name(),
                        "Max retries exceeded",
                        ["Examine exceptions to determine the root cause."],
                        exceptions,
                    ) from e

                if self._use_retry_recommendation:
                    delay = _extract_retry_after(e)
                else:
                    delay = None

                if delay is not None:
                    await asyncio.sleep(delay)
                else:
                    await asyncio.sleep(self._compute_delay(attempt))

        assert False, "Unreachable code"


class ExponentialRetry(RetryApproach):
    def __init__(
        self,
        max_tries: int,
        base: float = 2.0,
        jitter: bool = True,
        use_retry_recommendation: bool = True,
    ) -> None:
        if max_tries < 1:
            raise ValueError("max_tries must be >= 1")
        if max_tries > _MAX_RETRY_TIMES_EXPONETIAL:
            raise ValueError(f"max_tries must be <= {_MAX_RETRY_TIMES_EXPONETIAL}")
        if base < 1:
            raise ValueError("base must be >= 1")

        if base**max_tries > _MAX_RECOMONDED_RETRY_TIME_EXPONETIAL:
            warnings.warn(
                f"With base={base} and max_tries={max_tries}, the maximum delay could exceed {_MAX_RECOMONDED_RETRY_TIME_EXPONETIAL} seconds, which may be too long for some applications."
            )

        super().__init__(
            max_tries=max_tries, use_retry_recommendation=use_retry_recommendation
        )
        self._base = base
        self._jitter = jitter

    @classmethod
    def approach_name(cls) -> str:
        return "exponential"

    def _compute_delay(self, attempt: int) -> float:
        delay = self._base**attempt
        return random.uniform(0, delay) if self._jitter else delay


class LinearRetry(RetryApproach):
    def __init__(
        self,
        max_tries: int,
        step: float = 1.0,
        jitter: bool = True,
        use_retry_recommendation: bool = True,
    ) -> None:
        if max_tries < 1:
            raise ValueError("max_tries must be >= 1")
        if max_tries > _MAX_RETRY_TIMES_LINEAR:
            raise ValueError(f"max_tries must be <= {_MAX_RETRY_TIMES_LINEAR}")
        if step < 0:
            raise ValueError("step must be >= 0")

        super().__init__(
            max_tries=max_tries, use_retry_recommendation=use_retry_recommendation
        )
        self._step = step
        self._jitter = jitter

    @classmethod
    def approach_name(cls) -> str:
        return "linear"

    def _compute_delay(self, attempt: int) -> float:
        delay = self._step * (attempt + 1)
        return random.uniform(0, delay) if self._jitter else delay


class FixedRetry(RetryApproach):
    def __init__(
        self,
        max_tries: int,
        delay: float = 1.0,
        use_retry_recommendation: bool = True,
    ) -> None:
        if max_tries < 1:
            raise ValueError("max_tries must be >= 1")
        if max_tries > _MAX_RETRY_TIMES_FIXED:
            raise ValueError(f"max_tries must be <= {_MAX_RETRY_TIMES_FIXED}")
        if delay < 0:
            raise ValueError("delay must be >= 0")

        super().__init__(
            max_tries=max_tries, use_retry_recommendation=use_retry_recommendation
        )
        self._delay = delay

    @classmethod
    def approach_name(cls) -> str:
        return "fixed"

    def _compute_delay(self, attempt: int) -> float:
        return self._delay
