from __future__ import annotations

from collections import OrderedDict
from typing import Any

from typing_extensions import Never

from railtracks.context.central import get_session_identity, is_context_present
from railtracks.exceptions.errors import ContextError
from railtracks.middleware.core import Middleware

# Counters outlive their session so a finished run's budget stays readable.
# Keeping only the most recent bounds that without limiting real concurrency.
_MAX_TRACKED_SESSIONS = 64


class MaxCalls(Middleware[Any, Any, Never]):
    """Fail the wrapped call once it has been invoked ``max_calls`` times.

    Slot-agnostic: works both as node middleware (``middleware=``) and as model
    middleware (``model_middleware=``) — it only counts invocations of ``call``
    and never inspects the arguments::

        import railtracks as rt
        from railtracks.prebuilt import middleware

        rt.agent_node(
            "Agent",
            llm=rt.llm.OpenAILLM(model_name="gpt-5.4-mini"),
            middleware=[middleware.MaxCalls(5)],  # cap calls to the whole node
            model_middleware=[middleware.MaxCalls(5)],  # cap raw model calls
        )

    The count is tracked per session, resetting to zero when a new one begins. A
    single ``MaxCalls`` instance shared across nodes within the same session
    enforces a combined budget, while a fresh instance per node gives each its
    own limit. A bare top-level ``rt.call`` is its own run, so hold several calls
    under one budget by running them inside a ``Flow``.

    Finished sessions' counters stay readable via :attr:`call_count`, capped at
    the 64 most recent.

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
        # Keyed by session_id, or None outside a run; least-recently-used first.
        self._session_counts: OrderedDict[str | None, int] = OrderedDict()
        self._last_session_id: str | None = None
        super().__init__(self._middleware_fn)

    @property
    def max_calls(self) -> int:
        """The maximum number of calls allowed before raising."""
        return self._max_calls

    def _current_session_id(self) -> str | None:
        """Return the active session ID, or ``None`` if not inside a run."""
        if is_context_present():
            try:
                return get_session_identity().session_id
            except ContextError:
                return None
        return None

    def _inspection_key(self) -> str | None:
        """Return the live session, or the last counted one when outside a run."""
        if is_context_present():
            return self._current_session_id()
        return self._last_session_id

    @property
    def call_count(self) -> int:
        """Calls in the active session, or the run that just finished.

        Returns 0 for a session evicted by the 64-session retention cap.
        """
        return self._session_counts.get(self._inspection_key(), 0)

    def reset(self) -> None:
        """Reset the counter that :attr:`call_count` reads."""
        self._session_counts.pop(self._inspection_key(), None)

    def reset_all(self) -> None:
        """Reset call counters for all sessions."""
        self._session_counts.clear()
        self._last_session_id = None

    async def _middleware_fn(self, call, *args, **kwargs):
        # Live session only: a call outside a run must not spend a finished
        # run's budget, so unlike _inspection_key this never falls back.
        sess_id = self._current_session_id()
        # Read-modify-write is safe under one event loop: no await between them.
        current_count = self._session_counts.get(sess_id, 0)
        if current_count >= self._max_calls:
            if self._custom_message:
                raise MaxCallsExceededError(self._custom_message)
            raise MaxCallsExceededError("Maximum number of calls exceeded")
        self._session_counts[sess_id] = current_count + 1
        self._session_counts.move_to_end(sess_id)
        self._last_session_id = sess_id
        while len(self._session_counts) > _MAX_TRACKED_SESSIONS:
            self._session_counts.popitem(last=False)
        return await call(*args, **kwargs)


class MaxCallsExceededError(Exception):
    """Raised when a :class:`MaxCalls`-wrapped call is invoked past its limit."""
