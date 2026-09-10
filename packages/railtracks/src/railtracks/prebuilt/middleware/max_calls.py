from __future__ import annotations

import uuid
from collections import defaultdict
from typing import ClassVar

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

    _session_counts: ClassVar[dict[tuple[str, str], int]] = defaultdict(int)
    _lifetime_counts: ClassVar[dict[str, int]] = defaultdict(int)

    def __init__(
        self,
        max_calls: int,
        custom_message: str | None = None,
        *,
        per_run: bool = True,
    ):
        self._max_calls = max_calls
        self._budget_id = str(uuid.uuid4())
        self._custom_message = custom_message
        self._per_run = per_run
        super().__init__(self._middleware_fn)

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
        for the current session. Otherwise, returns the lifetime call count.
        """
        if self._per_run and is_context_present():
            try:
                sess_id = get_session_identity().session_id
                return self._session_counts.get((self._budget_id, sess_id), 0)
            except Exception:
                pass
        return self._lifetime_counts.get(self._budget_id, 0)

    @property
    def _call_count(self) -> int:
        return self.call_count

    @property
    def total_call_count(self) -> int:
        """The total number of calls made across all sessions for the lifetime of this instance."""
        return self._lifetime_counts.get(self._budget_id, 0)

    def reset(self, session_id: str | None = None) -> None:
        """Reset the call counter.

        Args:
            session_id: If provided, resets only the counter for that session ID.
                If None, clears all session counters and resets the lifetime counter for this budget.
        """
        if session_id is not None:
            self._session_counts.pop((self._budget_id, session_id), None)
        else:
            keys_to_remove = [
                k for k in self._session_counts if k[0] == self._budget_id
            ]
            for k in keys_to_remove:
                del self._session_counts[k]
            self._lifetime_counts.pop(self._budget_id, None)

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
            key = (self._budget_id, sess_id)
            current_count = self._session_counts.get(key, 0)
            if current_count >= self._max_calls:
                if self._custom_message:
                    raise MaxCallsExceededError(self._custom_message)
                raise MaxCallsExceededError("Maximum number of calls exceeded")
            self._session_counts[key] = current_count + 1
            self._lifetime_counts[self._budget_id] = (
                self._lifetime_counts.get(self._budget_id, 0) + 1
            )
        else:
            current_count = self._lifetime_counts.get(self._budget_id, 0)
            if current_count >= self._max_calls:
                if self._custom_message:
                    raise MaxCallsExceededError(self._custom_message)
                raise MaxCallsExceededError("Maximum number of calls exceeded")
            self._lifetime_counts[self._budget_id] = current_count + 1
        return await call(*args, **kwargs)


class MaxCallsExceededError(Exception):
    """Raised when a :class:`MaxCalls`-wrapped call is invoked past its limit."""
