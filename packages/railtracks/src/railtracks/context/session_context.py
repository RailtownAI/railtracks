from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
import queue
from typing import TYPE_CHECKING, Any

from railtracks.context.scope_link import ScopeLink
from railtracks.utils.config import ExecutorConfig

if TYPE_CHECKING:
    from railtracks.pubsub.publisher import RTPublisher


class ScopeKind(Enum):
    NODE = "node"
    MIDDLEWARE = "middleware"
    NODE_BODY = "node_body"
    LLM = "llm"


@dataclass(frozen=True)
class ScopeEntry:
    kind: ScopeKind
    id: str
    type_id: str | None = None

    def __post_init__(self):
        if self.kind == ScopeKind.MIDDLEWARE or self.kind == ScopeKind.LLM:
            if self.type_id is None:
                raise ValueError(f"ScopeEntry of kind {self.kind} must have a type_id.")


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
        flow_name: str | None = None,
        flow_id: str | None = None,
        session_name: str | None = None,
        stream_queue: asyncio.Queue[Any] | None = None,
    ):
        self._scope: ScopeLink[ScopeEntry] | None = scope
        self._publisher: RTPublisher | None = publisher
        self._session_id: str = session_id
        self._run_id: str | None = run_id
        self._executor_config: ExecutorConfig = executor_config
        self._flow_name: str | None = flow_name
        self._flow_id: str | None = flow_id
        self._session_name: str | None = session_name
        self._stream_queue: asyncio.Queue[Any] | None = stream_queue

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
    def current_llm_call_id(self) -> ScopeEntry | None:
        if self._scope is None:
            return None
        entry = self._scope.find(lambda e: e.kind is ScopeKind.LLM)
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

    @property
    def flow_name(self) -> str | None:
        return self._flow_name

    @property
    def flow_id(self) -> str | None:
        return self._flow_id

    @property
    def session_name(self) -> str | None:
        return self._session_name

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
            flow_name=self._flow_name,
            flow_id=self._flow_id,
            session_name=self._session_name,
        )

    @property
    def stream_queue(self) -> asyncio.Queue[Any] | None:
        """The queue that this frame's streamed LLM chunks are written to, or None.

        When set, the frame is the entry of a streamed invocation (see `rt.astream`): its
        LLM node writes each token chunk directly onto this queue, which the `Stream` handle
        on the calling side drains.
        """
        return self._stream_queue

    @stream_queue.setter
    def stream_queue(self, value: asyncio.Queue[Any]):
        self._stream_queue = value
