from .base import RetryApproach

_MAX_RETRY_TIMES_FIXED = 100


class FixedRetry(RetryApproach):
    """Fixed backoff: waits the same ``delay`` seconds before every retry.

    Useful when the provider's ``Retry-After`` header is unreliable or when
    you want predictable, uniform pacing.  Caps ``max_tries`` at 100.

    Args:
        max_tries: Total attempts (1–100).
        delay: Seconds to wait between attempts (>= 0).  Default ``1.0``.
    """

    def __init__(
        self,
        max_tries: int,
        delay: float = 1.0,
    ) -> None:
        if max_tries < 1:
            raise ValueError("max_tries must be >= 1")
        if max_tries > _MAX_RETRY_TIMES_FIXED:
            raise ValueError(f"max_tries must be <= {_MAX_RETRY_TIMES_FIXED}")
        if delay < 0:
            raise ValueError("delay must be >= 0")

        super().__init__(max_tries=max_tries)
        self._delay = delay

    @classmethod
    def approach_name(cls) -> str:
        return "fixed"

    def _compute_delay(self, attempt: int) -> float:
        return self._delay
