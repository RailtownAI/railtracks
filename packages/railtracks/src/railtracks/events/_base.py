from __future__ import annotations

import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, fields
from typing import TYPE_CHECKING, Generic, Literal, TypeVar

from typing_extensions import Self

if TYPE_CHECKING:
    from railtracks.context.scope_link import ScopeLink
    from railtracks.context.session_context import ScopeEntry


class Unset:
    """Sentinel type marking a field that was intentionally left unset (distinct from ``None``)."""

    _instance: Unset | None = None

    def __new__(cls) -> "Unset":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "UNSET"

    def __bool__(self) -> bool:
        return False


UNSET = Unset()


@dataclass(frozen=True)
class SpatialParent:
    pass


@dataclass(frozen=True)
class MiddlewareSpatialParent(SpatialParent):
    spatial_type: Literal["middleware"] = field(init=False, default="middleware")
    middleware_type_id: str


@dataclass(frozen=True)
class NodeSpatialParent(SpatialParent):
    spatial_type: Literal["node"] = field(init=False, default="node")
    node_id: str | None


@dataclass(frozen=True)
class NodeAndMiddlewareSpatialParent(SpatialParent):
    spatial_type: Literal["node_and_middleware"] = field(
        init=False, default="node_and_middleware"
    )
    node_id: str
    middleware_invoke_id: str | None


@dataclass(frozen=True)
class LLMAndMiddlewareSpatialParent(SpatialParent):
    spatial_type: Literal["llm_and_middleware"] = field(
        init=False, default="llm_and_middleware"
    )
    llm_invoke_id: str
    middleware_invoke_id: str | None


@dataclass(frozen=True)
class NoSpatialParent(SpatialParent):
    spatial_type: Literal["none"] = field(init=False, default="none")
    pass


@dataclass(frozen=True)
class Parent:
    pass


@dataclass(frozen=True)
class NodeParent(Parent):
    parent_type: Literal["node"] = field(init=False, default="node")
    node_id: str


@dataclass(frozen=True)
class MiddlewareParent(Parent):
    parent_type: Literal["middleware"] = field(init=False, default="middleware")
    middleware_type_id: str
    middleware_invoke_id: str


@dataclass(frozen=True)
class LLMParent(Parent):
    parent_type: Literal["llm"] = field(init=False, default="llm")
    llm_model_id: str
    llm_invoke_id: str


TSpatialParent = TypeVar("TSpatialParent", bound=SpatialParent)
TParent = TypeVar("TParent", bound=Parent)


@dataclass(kw_only=True)
class SessionEventBase(ABC, Generic[TSpatialParent]):
    spatial_parent: TSpatialParent | Unset = field(init=False, default=UNSET)

    timestamp: datetime.datetime = field(
        init=False,
        default_factory=lambda: datetime.datetime.now(tz=datetime.timezone.utc),
    )

    @abstractmethod
    def event_type(self) -> str:
        """
        Returns the type of the event.
        """
        ...

    def verify(self) -> None:
        for f in fields(self):
            value = getattr(self, f.name)

            if value is UNSET:
                raise ValueError(
                    f"Field '{f.name}' is unset in event {self.event_type()}"
                )

    def resolve_relationships(self, scope: ScopeLink[ScopeEntry] | None):
        """Resolve the event's spatial parent from the current scope chain.

        This is called by the bridge before publishing. Each event family implements
        its own resolver.
        """
        self.spatial_parent = self._get_spatial_parent(scope)

    @abstractmethod
    def _get_spatial_parent(
        self, scope: ScopeLink[ScopeEntry] | None
    ) -> TSpatialParent:
        """Return this event's spatial parent, given the ambient scope chain.

        Implemented per event family (each picks the matching resolver). The bridge
        calls this with `get_current_scope()` before publishing.
        """
        ...


@dataclass(kw_only=True)
class CreationEventBase(SessionEventBase[NoSpatialParent]):
    """A creation event is emitted before the created entity enters its own scope,
    so its parent resolves from the caller's ambient chain (no self-skip)."""

    def _get_spatial_parent(self, scope: ScopeLink[ScopeEntry] | None):
        return NoSpatialParent()


@dataclass(kw_only=True)
class ParentEventBase(
    SessionEventBase[TSpatialParent], Generic[TSpatialParent, TParent]
):
    """A parent event is emitted after the created entity enters its own scope,
    so its parent resolves from the caller's ambient chain (no self-skip)."""

    parent: TParent | Unset = field(init=False, default=UNSET)

    def resolve_relationships(self, scope: ScopeLink[ScopeEntry] | None):
        """Resolve the event's spatial parent and parent from the current scope chain.

        This is called by the bridge before publishing. Each event family implements
        its own resolver.
        """
        super().resolve_relationships(scope)
        self.parent = self._get_parent(scope)

    @abstractmethod
    def _get_parent(self, scope: ScopeLink[ScopeEntry] | None) -> TParent:
        pass


@dataclass(kw_only=True)
class FailureMixin:
    exception_name: str
    exception_message: str

    @classmethod
    def from_exception(cls, exc: Exception, **kwargs) -> Self:
        return cls(
            exception_name=type(exc).__name__,
            exception_message=str(exc),
            **kwargs,
        )
