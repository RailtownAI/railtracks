from __future__ import annotations

from contextlib import contextmanager
from typing import ContextManager, Protocol


class ScopeManager(Protocol):
    """Interface Middleware/Node use to signal scope changes."""

    def enter_node(self, node_id: str) -> ContextManager[None]: ...

    def enter_node_body(self) -> ContextManager[None]: ...

    def enter_middleware(self, name: str) -> ContextManager[str | None]: ...


class NullScopeManager:
    """No-op ScopeManager: pushes nothing, touches no global state."""

    @contextmanager
    def enter_node(self, node_id: str):
        yield

    @contextmanager
    def enter_node_body(self):
        yield

    @contextmanager
    def enter_middleware(self, name: str):
        yield None


_NULL_SCOPE_MANAGER = NullScopeManager()


def null_scope_manager() -> ScopeManager:
    """Shared no-op ScopeManager instance."""
    return _NULL_SCOPE_MANAGER
