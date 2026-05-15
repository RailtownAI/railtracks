import asyncio
import time
from abc import ABC, abstractmethod
from typing import Awaitable, Callable, TypeVar

import litellm

from .._exceptions import RetryError

_TResult = TypeVar("_TResult")

# Transient errors worth retrying.  Permanent errors (BadRequestError,
# AuthenticationError, etc.) are intentionally excluded — retrying them
# wastes quota and masks real bugs.
_RETRYABLE_EXCEPTIONS = (
    litellm.exceptions.RateLimitError,
    litellm.exceptions.Timeout,
    litellm.exceptions.InternalServerError,
    litellm.exceptions.ServiceUnavailableError,
    litellm.exceptions.APIConnectionError,
)


class RetryApproach(ABC):
    """Template base for retry strategies.

    Subclasses implement ``_compute_delay`` to define the backoff schedule.
    The retry loop and exception handling live here so subclasses stay minimal.

    Args:
        max_tries: Total attempts including the first call (not just retries).
    """

    def __init__(self, max_tries: int) -> None:
        if max_tries < 1:
            raise ValueError("max_tries must be >= 1")
        self._max_tries = max_tries

    @classmethod
    @abstractmethod
    def approach_name(cls) -> str:
        """Short identifier used in ``RetryError`` messages (e.g. ``"exponential"``)."""

    @abstractmethod
    def _compute_delay(self, attempt: int) -> float:
        """Seconds to wait before attempt ``attempt + 1`` (0-indexed)."""

    def call_with_retry(self, completion: Callable[[], _TResult]) -> _TResult:
        """Call ``completion`` up to ``max_tries`` times, sleeping between failures.

        Raises:
            RetryError: All attempts failed; ``exception_list`` holds every error.
            Exception: Any non-retryable exception propagates immediately.
        """
        exceptions: list[Exception] = []

        for attempt in range(self._max_tries):
            try:
                return completion()
            except _RETRYABLE_EXCEPTIONS as e:
                exceptions.append(e)
                if attempt == self._max_tries - 1:
                    raise RetryError(
                        self.approach_name(),
                        "Max retries exceeded",
                        ["Examine exceptions to determine the root cause."],
                        exceptions,
                    ) from e

                 
                time.sleep(self._compute_delay(attempt))

        assert False, "Unreachable code"

    async def acall_with_retry(
        self, completion: Callable[[], Awaitable[_TResult]]
    ) -> _TResult:
        """Async mirror of ``call_with_retry`` — awaits ``completion`` each attempt."""
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

                delay: float | None = None

                if delay is not None:
                    await asyncio.sleep(delay)
                else:
                    await asyncio.sleep(self._compute_delay(attempt))

        assert False, "Unreachable code"
