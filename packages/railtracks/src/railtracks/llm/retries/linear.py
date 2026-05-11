import random

from .base import RetryApproach

_MAX_RETRY_TIMES_LINEAR = 100



class LinearRetry(RetryApproach):
    """Linear backoff: delay = ``step * (attempt + 1)`` seconds.

    Grows steadily rather than exponentially — a middle ground between fixed
    and exponential when you expect short-lived rate limits.  Caps ``max_tries``
    at 100.

    Args:
        max_tries: Total attempts (1–100).
        step: Base increment in seconds (>= 0).  Default ``1.0`` gives 1 s, 2 s, 3 s …
        jitter: When ``True``, randomises the delay to ``uniform(0, step * (attempt+1))``.
    """

    def __init__(
        self,
        max_tries: int,
        step: float = 1.0,
        jitter: bool = True,
    ) -> None:
        if max_tries < 1:
            raise ValueError("max_tries must be >= 1")
        if max_tries > _MAX_RETRY_TIMES_LINEAR:
            raise ValueError(f"max_tries must be <= {_MAX_RETRY_TIMES_LINEAR}")
        if step < 0:
            raise ValueError("step must be >= 0")

        super().__init__(max_tries=max_tries)
        self._step = step
        self._jitter = jitter

    @classmethod
    def approach_name(cls) -> str:
        return "linear"

    def _compute_delay(self, attempt: int) -> float:
        delay = self._step * (attempt + 1)
        return random.uniform(0, delay) if self._jitter else delay
