from __future__ import annotations

from typing import Any

from railtracks.context.central import get_session_identity, is_context_present
from railtracks.middleware.core import Middleware


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

    The count is tracked per ``MaxCalls`` instance, so a single instance shared
    across nodes enforces a combined budget, while a fresh instance per node
    gives each its own limit.

    By default (``per_run=True``), the budget applies to each workflow run / session,
    resetting to zero when a new session begins. If ``per_run=False``, the budget
    accumulates across runs for the lifetime of this ``MaxCalls`` instance until
    explicitly reset via :meth:`reset`.

    Args:
        max_calls: Number of calls allowed before the limit is enforced.
        custom_message: Message to raise once the limit is exceeded. Defaults
            to ``"Maximum number of calls exceeded"``.
        per_run: If True (default), the budget resets per execution session / run.
            If False, the budget accumulates across multiple runs for the lifetime
            of this instance.

    Raises:
        MaxCallsExceededError: Once ``call`` has already been invoked
            ``max_calls`` times.
    """

    def __init__(
        self,
        max_calls: int,
        custom_message: str | None = None,
        *,
        per_run: bool = True,
    ):
        self._max_calls = max_calls
        self._call_count = 0
        self._custom_message = custom_message
        self._per_run = per_run
        self._session_counts: dict[str, int] = {}
        super().__init__(self._middleware_fn)

    def __deepcopy__(self, memo: dict[int, Any]) -> MaxCalls:
        memo[id(self)] = self
        return self

    @property
    def max_calls(self) -> int:
        """The maximum number of calls allowed before raising."""
        return self._max_calls

    @property
    def per_run(self) -> bool:
        """Whether the budget resets per execution session / run."""
        return self._per_run

    @property
    def call_count(self) -> int:
        """The current number of calls made against this budget.

        When ``per_run=True`` and inside an active session, returns the call count
        for the current session. Otherwise, returns the instance-level call count.
        """
        if self._per_run and is_context_present():
            try:
                sess_id = get_session_identity().session_id
                return self._session_counts.get(sess_id, 0)
            except Exception:
                pass
        return self._call_count

    @property
    def total_call_count(self) -> int:
        """The total number of calls made across all sessions for the lifetime of this instance."""
        return self._call_count

    def reset(self, session_id: str | None = None) -> None:
        """Reset the call counter.

        Args:
            session_id: If provided, resets only the counter for that session ID.
                If None, clears all session counters and resets the instance counter.
        """
        if session_id is not None:
            self._session_counts.pop(session_id, None)
        else:
            self._session_counts.clear()
            self._call_count = 0

    async def _middleware_fn(self, call, *args, **kwargs):
        in_session = False
        sess_id = None
        if self._per_run and is_context_present():
            try:
                sess_id = get_session_identity().session_id
                in_session = True
            except Exception:
                in_session = False

        if in_session and sess_id is not None:
            current_count = self._session_counts.get(sess_id, 0)
            if current_count >= self._max_calls:
                if self._custom_message:
                    raise MaxCallsExceededError(self._custom_message)
                raise MaxCallsExceededError("Maximum number of calls exceeded")
            self._session_counts[sess_id] = current_count + 1
            self._call_count += 1
        else:
            if self._call_count >= self._max_calls:
                if self._custom_message:
                    raise MaxCallsExceededError(self._custom_message)
                raise MaxCallsExceededError("Maximum number of calls exceeded")
            self._call_count += 1
        return await call(*args, **kwargs)


class MaxCallsExceededError(Exception):
    """Raised when a :class:`MaxCalls`-wrapped call is invoked past its limit."""
