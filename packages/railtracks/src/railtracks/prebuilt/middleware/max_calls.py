from __future__ import annotations

from collections import OrderedDict

from railtracks.context.central import get_session_identity, is_context_present
from railtracks.exceptions.errors import ContextError
from railtracks.middleware.core import Middleware

_MAX_TRACKED_SESSIONS = 64
"""Upper bound on the per-session counters a single ``MaxCalls`` retains.

Counters outlive the session that produced them so the budget stays readable
once a run is over. Retaining the most recent ``_MAX_TRACKED_SESSIONS`` bounds
that memory without capping how many runs may overlap in practice.
"""


class MaxCalls(Middleware):
    """Fail the wrapped call once it has been invoked ``max_calls`` times.

    Slot-agnostic: works both as node middleware (``middleware=``) and as model
    middleware (``model_middleware=``) — it only counts invocations of ``call``
    and never inspects the arguments::

        import railtracks as rt
        from railtracks.prebuilt import middleware

        rt.agent_node(
            "Agent",
            llm=rt.llm.OpenAILLM(model_name="gpt-4o"),
            middleware=[middleware.MaxCalls(5)],  # cap calls to the whole node
            model_middleware=[middleware.MaxCalls(5)],  # cap raw model calls
        )

    The count is tracked per workflow run / session, resetting to zero when a new
    session begins. A single ``MaxCalls`` instance shared across nodes within the
    same run enforces a combined budget, while a fresh instance per node gives
    each its own limit.

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
        # Keyed by session_id (str) when inside a run; None when outside. Each
        # session gets its own independent counter, ordered least- to
        # most-recently used so the oldest can be evicted at the cap.
        self._session_counts: OrderedDict[str | None, int] = OrderedDict()
        # Session whose counter was incremented last, so the budget spent by a
        # finished run stays readable after its context is gone.
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
        """Return the session that :attr:`call_count` and :meth:`reset` act on.

        Inside a run that is the live session. Outside one it is the most
        recently counted session, so reading the budget after ``flow.invoke()``
        returns what that run actually spent rather than zero.
        """
        if is_context_present():
            return self._current_session_id()
        return self._last_session_id

    @property
    def call_count(self) -> int:
        """Calls made against this budget in the active session.

        Outside a run, reports the most recently counted session instead, which
        is the run that just finished.
        """
        return self._session_counts.get(self._inspection_key(), 0)

    def reset(self) -> None:
        """Reset the call counter that :attr:`call_count` reads.

        Inside a run that is the active session's counter. Outside one it is the
        most recently counted session's.
        """
        self._session_counts.pop(self._inspection_key(), None)

    def reset_all(self) -> None:
        """Reset call counters for all sessions."""
        self._session_counts.clear()
        self._last_session_id = None

    async def _middleware_fn(self, call, *args, **kwargs):
        # Always the live session: a call made outside a run must never spend a
        # finished run's budget, so this deliberately does not fall back the way
        # _inspection_key does.
        sess_id = self._current_session_id()
        # Read-modify-write is safe under a single event loop (no await
        # between the read and the write).
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
