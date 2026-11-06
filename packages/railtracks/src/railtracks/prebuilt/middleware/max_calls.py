from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from typing_extensions import Never

from railtracks.context.central import is_context_present
from railtracks.context.operations import local
from railtracks.middleware.core import Middleware


@dataclass
class _CallCount:
    calls: int = 0


class MaxCalls(Middleware[Any, Any, Never]):
    """Fail the wrapped call once it has been invoked ``max_calls`` times.

    Slot-agnostic: works both as node middleware (``middleware=``) and as model
    middleware (``model_middleware=``) — it only counts invocations of ``call``
    and never inspects the arguments::

        import railtracks as rt
        from railtracks.prebuilt import middleware

        rt.agent_node(
            "Agent",
            llm=rt.llm.OpenAILLM(model_name="gpt-6-luna"),
            middleware=[middleware.MaxCalls(5)],  # cap calls to the whole node
            model_middleware=[middleware.MaxCalls(5)],  # cap raw model calls
        )

    The count is kept per session in ``rt.context.local``, starting from zero in
    every session, concurrent ones included. A single ``MaxCalls`` instance shared
    across nodes within the same session enforces a combined budget, while a fresh
    instance per node gives each its own limit. A bare top-level ``rt.call`` is its
    own run, so hold several calls under one budget by running them inside a
    ``Flow``.

    Outside a run, :attr:`call_count` reads the most recent run's count, so a
    finished run's spend stays readable.

    Args:
        max_calls: Number of calls allowed before the limit is enforced.
        custom_message: Message to raise once the limit is exceeded. Defaults
            to ``"Maximum number of calls exceeded"``.

    Raises:
        MaxCallsExceededError: Once ``call`` has already been invoked
            ``max_calls`` times.
    """

    def __init__(
        self,
        max_calls: int,
        custom_message: str | None = None,
    ):
        self._max_calls = max_calls
        self._custom_message = custom_message
        # calls made outside any run count here
        self._unscoped = _CallCount()
        # what call_count reads outside a run: the most recent run's count
        self._last = self._unscoped
        super().__init__(self._middleware_fn)

    @property
    def max_calls(self) -> int:
        """The maximum number of calls allowed before raising."""
        return self._max_calls

    def _count(self) -> _CallCount:
        """The active session's count, or outside a run, the most recent one."""
        if is_context_present():
            self._last = local(_CallCount, owner=self)
        return self._last

    @property
    def call_count(self) -> int:
        """Calls in the active session, or outside a run, in the most recent one."""
        return self._count().calls

    def reset(self) -> None:
        """Reset the counter that :attr:`call_count` reads."""
        self._count().calls = 0

    def reset_all(self) -> None:
        """Reset the counter that :attr:`call_count` reads.

        Each session's counter ends with its session, so the most recent one is the
        only counter left to reset; this is the same as :meth:`reset`.
        """
        self.reset()

    async def _middleware_fn(self, call, *args, **kwargs):
        if not is_context_present():
            # a call outside any run must not spend a finished run's budget
            self._last = self._unscoped
        count = self._count()
        # Read-modify-write is safe under one event loop: no await between them.
        if count.calls >= self._max_calls:
            if self._custom_message:
                raise MaxCallsExceededError(self._custom_message)
            raise MaxCallsExceededError("Maximum number of calls exceeded")
        count.calls += 1
        return await call(*args, **kwargs)


class MaxCallsExceededError(Exception):
    """Raised when a :class:`MaxCalls`-wrapped call is invoked past its limit."""
