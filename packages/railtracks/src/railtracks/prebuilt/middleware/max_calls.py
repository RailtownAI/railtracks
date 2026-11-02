from __future__ import annotations

from typing import Any

from typing_extensions import Never

from railtracks.middleware.core import Middleware
from railtracks.middleware.run_local import RunLocal


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

    The count is per run (a :class:`~railtracks.middleware.RunLocal`), starting
    from zero in every run, concurrent runs included. A single ``MaxCalls``
    instance shared across nodes enforces a combined budget within each run, while
    a fresh instance per node gives each its own limit. A bare top-level
    ``rt.call`` is its own run, so hold several calls under one budget by running
    them inside a ``Flow``.

    Args:
        max_calls: Number of calls allowed before the limit is enforced.
        custom_message: Message to raise once the limit is exceeded. Defaults
            to ``"Maximum number of calls exceeded"``.

    Raises:
        MaxCallsExceededError: Once ``call`` has already been invoked
            ``max_calls`` times.
    """

    _calls = RunLocal(int)

    def __init__(
        self,
        max_calls: int,
        custom_message: str | None = None,
    ):
        self._max_calls = max_calls
        self._custom_message = custom_message
        super().__init__(self._middleware_fn)

    @property
    def max_calls(self) -> int:
        """The maximum number of calls allowed before raising."""
        return self._max_calls

    @property
    def call_count(self) -> int:
        """Calls in the active run, or outside a run, in the most recent one."""
        return self._calls

    def reset(self) -> None:
        """Reset the counter that :attr:`call_count` reads."""
        del self._calls

    def reset_all(self) -> None:
        """Reset the counter that :attr:`call_count` reads.

        Each run's counter ends with its run, so the most recent one is the only
        counter left to reset; this is the same as :meth:`reset`.
        """
        self.reset()

    async def _middleware_fn(self, call, *args, **kwargs):
        # Read-modify-write is safe under one event loop: no await between them.
        if self._calls >= self._max_calls:
            if self._custom_message:
                raise MaxCallsExceededError(self._custom_message)
            raise MaxCallsExceededError("Maximum number of calls exceeded")
        self._calls += 1
        return await call(*args, **kwargs)


class MaxCallsExceededError(Exception):
    """Raised when a :class:`MaxCalls`-wrapped call is invoked past its limit."""
