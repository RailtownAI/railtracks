import random
import warnings

from .base import RetryApproach

_MAX_RECOMONDED_RETRY_TIME_EXPONETIAL = (
    1000  # 1000 seconds feels like a reasonable bound
)
_MAX_RETRY_TIMES_EXPONETIAL = 20


class ExponentialRetry(RetryApproach):
    """Exponential backoff: delay = ``base ** attempt`` seconds.

    Caps ``max_tries`` at 20 to prevent runaway wait times.  Warns if the
    theoretical maximum delay exceeds 1 000 s.

    Args:
        max_tries: Total attempts (1–20).
        base: Backoff multiplier (>= 1.0).  Default ``2.0`` gives 1 s, 2 s, 4 s …
        jitter: When ``True``, randomises the delay to ``uniform(0, base**attempt)``
            to spread load across concurrent callers.
    """

    def __init__(
        self,
        max_tries: int,
        base: float = 2.0,
        jitter: bool = True,
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
            max_tries=max_tries,
        )
        self._base = base
        self._jitter = jitter

    @classmethod
    def approach_name(cls) -> str:
        return "exponential"

    def _compute_delay(self, attempt: int) -> float:
        delay = self._base**attempt
        return random.uniform(0, delay) if self._jitter else delay
