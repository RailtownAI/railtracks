from __future__ import annotations

import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Generic, TypeVar


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


TSpatialParent = TypeVar("TSpatialParent", bound=SpatialParent)


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
        assert self.spatial_parent != UNSET, (
            "Spatial parent should be resolved before publishing the event."
        )
