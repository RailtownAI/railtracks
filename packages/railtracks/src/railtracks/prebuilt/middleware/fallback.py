from __future__ import annotations

from typing import TYPE_CHECKING, Any

from typing_extensions import Never

from railtracks.context.central import get_current_scope, is_context_present
from railtracks.context.session_context import ScopeKind
from railtracks.exceptions.errors import LLMError
from railtracks.interaction._call import call as call_node
from railtracks.middleware.core import Middleware
from railtracks.nodes.nodes import Node

if TYPE_CHECKING:
    from railtracks.built_nodes.function.base import RTFunction

_DEFAULT_ON: tuple[type[Exception], ...] = (LLMError,)


class Fallback(Middleware[Any, Any, Never]):
    """Hand the input to backup nodes, in order, when the wrapped node fails.

    Node-level middleware (attach it on ``middleware=``, not
    ``model_middleware=``). Each attempt is a real node run through
    ``rt.call``, so every backup is recorded in the session like any other
    node. The common case is an agent whose model is unreliable — a small
    on-device model, a provider outage, rate limits — where the backups are
    the same agent built on other models::

        import railtracks as rt
        from railtracks.prebuilt import middleware

        Primary = rt.agent_node(
            "Agent",
            llm=rt.llm.OpenAILLM(model_name="gpt-4o-mini"),
            middleware=[middleware.Fallback(ClaudeBackup, LunaBackup)],
        )

    A backup starts from the original input; it does not see the primary's
    partial work, so any tools the primary already ran will run again. Backups
    must accept the same input as the wrapped node. Re-entering the same
    ``Fallback`` instance from inside one of its own attempts — a backup that
    carries it, or two instances pointed at each other — runs the node plainly
    instead of looping forever.

    Args:
        backups: The backup nodes, tried in order after the wrapped call
            raises an error in ``on``. At least one is required.
        on: Exception types that trigger a fallback attempt. Defaults to
            ``(LLMError,)`` — what a failed model call becomes at the node
            level. Widen or narrow it like ``Retry``'s ``retry_on``; anything
            not in the tuple propagates immediately.
    """

    def __init__(
        self,
        *backups: type[Node[Any, Any]] | RTFunction[Any, Any],
        on: tuple[type[Exception], ...] | None = None,
    ):
        if not backups:
            raise ValueError("Fallback requires at least one backup node")
        for backup in backups:
            node_cls = backup.node_type if hasattr(backup, "node_type") else backup
            if not (isinstance(node_cls, type) and issubclass(node_cls, Node)):
                raise TypeError(f"Fallback backups must be nodes, got {backup!r}")
        self._backups = backups
        self._on = _DEFAULT_ON if on is None else on
        super().__init__(self._middleware_fn)

    def _is_reentry(self) -> bool:
        """Whether this instance already sits on the scope chain of the attempt
        that dispatched into this call — i.e. the call arrived through one of
        its own backups."""
        if not is_context_present():
            return False
        scope = get_current_scope()
        if scope is None:
            return False
        # The head of the chain is this invocation's own MIDDLEWARE entry, so
        # skip it; a match further up means this instance is re-entering.
        return (
            scope.find(
                lambda e: e.kind is ScopeKind.MIDDLEWARE and e.type_id == self.type_id,
                skip=1,
            )
            is not None
        )

    async def _middleware_fn(self, call, *args, **kwargs):
        if self._is_reentry():
            return await call(*args, **kwargs)
        try:
            return await call(*args, **kwargs)
        except self._on as error:
            last_error = error
        for backup in self._backups:
            try:
                return await call_node(backup, *args, **kwargs)
            except self._on as error:
                last_error = error
        raise last_error
