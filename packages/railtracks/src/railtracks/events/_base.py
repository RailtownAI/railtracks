from __future__ import annotations

import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, fields
from typing import TYPE_CHECKING, Generic, TypeVar

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
    middleware_id: str


@dataclass(frozen=True)
class NodeSpatialParent(SpatialParent):
    node_id: str
    middleware_id: str | None = None


@dataclass(frozen=True)
class LLMSpatialParent(SpatialParent):
    llm_id: str
    middleware_id: str | None = None


@dataclass(frozen=True)
class NoSpatialParent(SpatialParent):
    pass


@dataclass(frozen=True)
class Parent:
    pass


@dataclass(frozen=True)
class NodeParent(Parent):
    node_id: str

@dataclass(frozen=True)
class MiddlewareParent(Parent):
    middleware_id: str
    middleware_invoke_id: str

@dataclass(frozen=True)
class LLMParent(Parent):
    llm_model_id: str
    llm_invoke_id: str

TSpatialParent = TypeVar("TSpatialParent", bound=SpatialParent)
TParent = TypeVar("TParent", bound=Parent)

@dataclass(kw_only=True)
class SessionEventBase(ABC, Generic[TSpatialParent]):
    spatial_parent: TSpatialParent | Unset = UNSET

    timestamp: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(tz=datetime.timezone.utc)
    )

    @abstractmethod
    def event_type(self) -> str:
        """
        Returns the type of the event.
        """
        ...

    def verify(self) -> None:
        for field in fields(self):
            value = getattr(self, field.name)

            if value is UNSET:
                raise ValueError(f"Field '{field.name}' is unset in event {self.event_type()}")

    def resolve_relationships(self, scope: ScopeLink[ScopeEntry] | None):
        """Resolve the event's spatial parent from the current scope chain.

        This is called by the bridge before publishing. Each event family implements
        its own resolver.
        """
        self.spatial_parent = self._get_spatial_parent(scope)
    
    @abstractmethod
    def _get_spatial_parent(self, scope: ScopeLink[ScopeEntry] | None) -> TSpatialParent:
        """Return this event's spatial parent, given the ambient scope chain.

        Implemented per event family (each picks the matching resolver). The bridge
        calls this with `get_current_scope()` before publishing.
        """
        ...

    

class CreationEventBase(SessionEventBase[NoSpatialParent]):
    """A creation event is emitted before the created entity enters its own scope,
    so its parent resolves from the caller's ambient chain (no self-skip)."""
    def _get_spatial_parent(self, scope: ScopeLink[ScopeEntry] | None):
        return NoSpatialParent()




class ParentEventBase(SessionEventBase[TSpatialParent], Generic[TSpatialParent, TParent]):
    """A parent event is emitted after the created entity enters its own scope,
    so its parent resolves from the caller's ambient chain (no self-skip)."""

    parent: TParent | Unset = UNSET


    def resolve_relationships(self, scope: ScopeLink[ScopeEntry] | None):
        """Resolve the event's spatial parent and parent from the current scope chain.

        This is called by the bridge before publishing. Each event family implements
        its own resolver.
        """
        super().resolve_relationships(scope)
        self.parent = self._get_parent(scope)

    
    @abstractmethod
    def _get_parent(self, scope: ScopeLink[ScopeEntry] | None) -> TParent:
        # do nothing
        pass
