from __future__ import annotations

from types import MemberDescriptorType
from typing import Any

from typing_extensions import Never

from railtracks.exceptions import (
    DecisionModelError,
    DecisionRateLimitError,
    DecisionRefusalError,
    DecisionTimeoutError,
)
from railtracks.llm import RetryError
from railtracks.llm.retries import ExponentialRetry, RetryApproach
from railtracks.llm.retries.base import _RETRYABLE_EXCEPTIONS
from railtracks.middleware.core import Middleware

_DEFAULT_RETRY_ON = (
    *_RETRYABLE_EXCEPTIONS,
    DecisionTimeoutError,
    DecisionRateLimitError,
)


def _exhausted_decision_error(
    last: DecisionModelError, failures: list[Exception]
) -> DecisionModelError:
    """Copy a decision failure without invoking a user subclass's constructor."""
    error = BaseException.__new__(type(last))
    error.args = last.args
    error.__dict__.update(last.__dict__)
    for cls in type(last).__mro__:
        for name, descriptor in vars(cls).items():
            if isinstance(descriptor, MemberDescriptorType) and hasattr(last, name):
                setattr(error, name, getattr(last, name))
    error.notes = [*last.notes, f"Gave up after {len(failures)} attempts."]
    if hasattr(last, "__notes__"):
        error.__notes__ = list(last.__notes__)
    if isinstance(error, DecisionRefusalError):
        error.refused = list(error.refused)
        error.answers = dict(error.answers)
    error.retry_exhausted = True
    error.retry_errors = tuple(failures)
    return error


class Retry(Middleware[Any, Any, Never]):
    """Retry the wrapped call when it raises a transient error.

    Slot-agnostic: works both as node middleware (``middleware=``) and as model
    middleware (``model_middleware=``) — it only re-invokes ``call`` and never
    inspects the arguments::

        import railtracks as rt
        from railtracks.prebuilt import middleware

        rt.agent_node(
            "Agent",
            llm=rt.llm.OpenAILLM(model_name="gpt-6-luna"),
            middleware=[middleware.Retry(3)],  # retry the whole node
            model_middleware=[middleware.Retry(3)],  # retry each raw model call
        )

    The backoff schedule is delegated to a :class:`~railtracks.llm.retries.RetryApproach`
    (the same strategies used by ``retry_approach`` on model objects).

    Args:
        max_tries: Total attempts including the first call. Ignored when
            ``approach`` is given.
        approach: Backoff strategy; defaults to
            :class:`~railtracks.llm.retries.ExponentialRetry` with ``max_tries``.
        retry_on: Exception types worth retrying. Defaults to the transient LLM
            provider errors (rate limits, timeouts, connection failures) and
            decision-node timeouts and rate limits. Pass your own tuple to replace
            these defaults. Anything not in the tuple propagates immediately.

    Raises:
        DecisionModelError: Decision errors exhausted the attempts. A fresh error
            preserves the last error's type, provider cause and attributes, with
            an exhaustion note and the attempts in ``retry_errors``.
        RetryError: Other retryable errors exhausted the attempts.
        Exception: Non-retryable errors and errors marked ``retry_exhausted``
            propagate immediately, without spending an outer layer's budget.
    """

    def __init__(
        self,
        max_tries: int = 3,
        *,
        approach: RetryApproach | None = None,
        retry_on: tuple[type[Exception], ...] | None = None,
    ):
        self._approach = (
            approach if approach is not None else ExponentialRetry(max_tries=max_tries)
        )
        self._retry_on = retry_on if retry_on is not None else _DEFAULT_RETRY_ON
        super().__init__(self._middleware_fn)

    async def _middleware_fn(self, call, *args, **kwargs):
        try:
            return await self._approach.acall_with_retry(
                lambda: call(*args, **kwargs), retry_on=self._retry_on
            )
        except RetryError as e:
            last = e.exception_list[-1] if e.exception_list else None
            if not isinstance(last, DecisionModelError):
                raise
            error = _exhausted_decision_error(last, e.exception_list)
            raise error from last.__cause__
