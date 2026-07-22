from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from railtracks.context.scope_link import ScopeLink
from railtracks.utils.config import ExecutorConfig

if TYPE_CHECKING:
    from railtracks.pubsub.publisher import RTPublisher


class ScopeKind(Enum):
    NODE = "node"
    MIDDLEWARE = "middleware"
    NODE_BODY = "node_body"


@dataclass(frozen=True)
class ScopeEntry:
    kind: ScopeKind
    id: str
    name: str | None = None


class SessionContext:
    """
    The SessionContext class is used to store global variables designed to be used in the RT system.

    The tooling in the class is very tightly dependent on the requirements of the RT system.
    """

    def __init__(
        self,
        *,
        session_id: str,
        run_id: str | None = None,
        publisher: RTPublisher | None = None,
        scope: ScopeLink[ScopeEntry] | None = None,
        executor_config: ExecutorConfig,
    ):
        self._scope: ScopeLink[ScopeEntry] | None = scope
        self._publisher: RTPublisher | None = publisher
        self._session_id: str = session_id
        self._run_id: str | None = run_id
        self._executor_config: ExecutorConfig = executor_config

    @property
    def executor_config(self) -> ExecutorConfig:
        """
        Returns the executor configuration for this run.
        """
        return self._executor_config

    @executor_config.setter
    def executor_config(self, value: ExecutorConfig):
        """
        Sets the executor configuration for this run.
        """
        self._executor_config = value

    @property
    def scope(self) -> ScopeLink[ScopeEntry] | None:
        return self._scope

    @property
    def current_node_id(self) -> ScopeEntry | None:
        if self._scope is None:
            return None
        entry = self._scope.find(
            lambda e: e.kind in (ScopeKind.NODE, ScopeKind.NODE_BODY)
        )
        return entry

    @property
    def current_middleware_id(self) -> ScopeEntry | None:
        if self._scope is None:
            return None
        entry = self._scope.find(lambda e: e.kind is ScopeKind.MIDDLEWARE)
        return entry

    @property
    def is_in_node_body(self) -> bool:
        last_entry = self.current_node_id
        if last_entry is None:
            return False

        return last_entry.kind is ScopeKind.NODE_BODY

    @property
    def is_active(self) -> bool:
        """
        Check if the internal context has been defined.
        """
        if self._publisher is None:
            return False

        return self._publisher.is_running()

    @property
    def publisher(self):
        return self._publisher

    @publisher.setter
    def publisher(self, value: RTPublisher):
        self._publisher = value

    @property
    def session_id(self) -> str:
        return self._session_id

    @session_id.setter
    def session_id(self, value: str):
        self._session_id = value

    @property
    def run_id(self) -> str | None:
        return self._run_id

    def with_scope_pushed(
        self, entry: ScopeEntry, *, run_id: str | None = None
    ) -> SessionContext:
        """Returns a new SessionContext with `entry` pushed onto the scope chain."""
        new_scope = ScopeLink(value=entry, parent=self._scope)
        resolved_run_id = self._run_id if run_id is None else run_id

        return SessionContext(
            session_id=self._session_id,
            run_id=resolved_run_id,
            publisher=self._publisher,
            scope=new_scope,
            executor_config=self._executor_config,
        )
