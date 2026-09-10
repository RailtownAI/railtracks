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

    _counts: ClassVar[dict[tuple[str, str | None], int]] = defaultdict(int)

    def __init__(
        self,
        max_calls: int,
        custom_message: str | None = None,
    ):
        self._max_calls = max_calls
        self._budget_id = str(uuid.uuid4())
        self._custom_message = custom_message
        super().__init__(self._middleware_fn)

    @property
    def max_calls(self) -> int:
        """The maximum number of calls allowed before raising."""
        return self._max_calls

    def _get_current_key(self) -> tuple[str, str | None]:
        sess_id = None
        if is_context_present():
            try:
                sess_id = get_session_identity().session_id
            except Exception:
                sess_id = None
        return (self._budget_id, sess_id)

    @property
    def call_count(self) -> int:
        """The current number of calls made against this budget in the active session."""
        return self._counts.get(self._get_current_key(), 0)

    @property
    def _call_count(self) -> int:
        return self.call_count

    def reset(self, session_id: str | None = None) -> None:
        """Reset the call counter.

        Args:
            session_id: If provided, resets only the counter for that session ID.
                If None, clears all session counters for this budget.
        """
        if session_id is not None:
            self._counts.pop((self._budget_id, session_id), None)
        else:
            keys_to_remove = [k for k in self._counts if k[0] == self._budget_id]
            for k in keys_to_remove:
                del self._counts[k]

    async def _middleware_fn(self, call, *args, **kwargs):
        key = self._get_current_key()
        current_count = self._counts.get(key, 0)
        if current_count >= self._max_calls:
            if self._custom_message:
                raise MaxCallsExceededError(self._custom_message)
            raise MaxCallsExceededError("Maximum number of calls exceeded")
        self._counts[key] = current_count + 1
        return await call(*args, **kwargs)


class MaxCallsExceededError(Exception):
    """Raised when a :class:`MaxCalls`-wrapped call is invoked past its limit."""
