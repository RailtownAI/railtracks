from __future__ import annotations

import datetime
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field, fields
from enum import Enum
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


class SpatialType(str, Enum):
    """Discriminator tag for the ``SpatialParent`` union. ``str`` base means the
    member serializes as its ``.value`` through ``json.dumps`` and satisfies the
    registry's ``Literal`` → ``ColumnKind.STRING`` check."""

    MIDDLEWARE = "middleware"
    NODE = "node"
    NODE_AND_MIDDLEWARE = "node_and_middleware"
    LLM_AND_MIDDLEWARE = "llm_and_middleware"
    NONE = "none"


@dataclass(frozen=True)
class SpatialParent:
    def __post_init__(self):
        if not hasattr(self, "type"):
            raise ValueError(
                f"SpatialParent subclass {self.__class__.__name__} must define a 'type' field."
            )

    def encode(self):
        return asdict(self)


@dataclass(frozen=True)
class MiddlewareSpatialParent(SpatialParent):
    type: Literal[SpatialType.MIDDLEWARE] = field(
        init=False, default=SpatialType.MIDDLEWARE
    )
    middleware_invoke_id: str


@dataclass(frozen=True)
class NodeSpatialParent(SpatialParent):
    type: Literal[SpatialType.NODE] = field(init=False, default=SpatialType.NODE)
    node_id: str | None


@dataclass(frozen=True)
class NodeAndMiddlewareSpatialParent(SpatialParent):
    type: Literal[SpatialType.NODE_AND_MIDDLEWARE] = field(
        init=False, default=SpatialType.NODE_AND_MIDDLEWARE
    )
    node_id: str
    middleware_invoke_id: str | None


@dataclass(frozen=True)
class LLMAndMiddlewareSpatialParent(SpatialParent):
    type: Literal[SpatialType.LLM_AND_MIDDLEWARE] = field(
        init=False, default=SpatialType.LLM_AND_MIDDLEWARE
    )
    llm_invoke_id: str
    middleware_invoke_id: str | None


@dataclass(frozen=True)
class NoSpatialParent(SpatialParent):
    type: Literal[SpatialType.NONE] = field(init=False, default=SpatialType.NONE)


class ParentType(str, Enum):
    """Discriminator tag for the ``Parent`` union. ``str`` base means the member
    serializes as its ``.value`` through ``json.dumps`` and satisfies the
    registry's ``Literal`` → ``ColumnKind.STRING`` check."""

    NODE = "node"
    MIDDLEWARE = "middleware"
    LLM = "llm"


@dataclass(frozen=True)
class Parent:
    def __post_init__(self):
        if not hasattr(self, "type"):
            raise ValueError(
                f"Parent subclass {self.__class__.__name__} must define a 'type' field."
            )

    def encode(self):
        return asdict(self)


@dataclass(frozen=True)
class NodeParent(Parent):
    type: Literal[ParentType.NODE] = field(init=False, default=ParentType.NODE)
    node_id: str


@dataclass(frozen=True)
class MiddlewareParent(Parent):
    type: Literal[ParentType.MIDDLEWARE] = field(
        init=False, default=ParentType.MIDDLEWARE
    )
    middleware_type_id: str
    middleware_invoke_id: str


@dataclass(frozen=True)
class LLMParent(Parent):
    type: Literal[ParentType.LLM] = field(init=False, default=ParentType.LLM)
    llm_type_id: str
    llm_invoke_id: str


TSpatialParent = TypeVar("TSpatialParent", bound=SpatialParent)
TParent = TypeVar("TParent", bound=Parent)


@dataclass(kw_only=True)
class SessionEventBase(ABC, Generic[TSpatialParent]):
    spatial_parent: TSpatialParent | Unset = field(
        init=False, default=UNSET, metadata={"flatten": True}
    )

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

    def encode(self):
        encoded_json = {}
        for f in fields(self):
            if f.metadata.get("flatten", False):
                inner_dict = getattr(self, f.name).encode()
                for inner_key, inner_value in inner_dict.items():
                    name = f"{f.name}_{inner_key}"
                    encoded_json[name] = inner_value
            else:
                encoded_json[f.name] = getattr(self, f.name)
        return encoded_json


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

    parent: TParent | Unset = field(
        init=False, default=UNSET, metadata={"flatten": True}
    )

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
