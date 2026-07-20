from __future__ import annotations

from railtracks.llm.retries import ExponentialRetry, RetryApproach
from railtracks.middleware.core import Middleware


class Retry(Middleware):
    """Retry the wrapped call when it raises a transient error.

    Slot-agnostic: works both as node middleware (``middleware=``) and as model
    middleware (``model_middleware=``) — it only re-invokes ``call`` and never
    inspects the arguments::

        import railtracks as rt
        from railtracks import middleware

        rt.agent_node(
            "Agent",
            llm=rt.llm.OpenAILLM(model_name="gpt-4o"),
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
            provider errors (rate limits, timeouts, connection failures) — pass
            your own tuple (e.g. ``(Exception,)``) for node-level use. Anything
            not in the tuple propagates immediately.
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
        self._retry_on = retry_on
        super().__init__(self._middleware_fn)

    async def _middleware_fn(self, call, *args, **kwargs):
        return await self._approach.acall_with_retry(
            lambda: call(*args, **kwargs), retry_on=self._retry_on
        )
