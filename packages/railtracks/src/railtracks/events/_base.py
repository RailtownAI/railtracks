from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Generic, TypeVar
import datetime


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
class Parent:
    pass


@dataclass(frozen=True)
class MiddlewareParent(Parent):
    middleware_id: str


@dataclass(frozen=True)
class NodeParent(Parent):
    node_id: str
    middleware_id: str | None = None


@dataclass(frozen=True)
class LLMParent(Parent):
    llm_id: str
    middleware_id: str | None = None


@dataclass(frozen=True)
class NoParent(Parent):
    pass


TParent = TypeVar("TParent", bound=Parent)


@dataclass(kw_only=True)
class SessionEventBase(ABC, Generic[TParent]):
    parent: TParent | Unset = UNSET
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)

    @abstractmethod
    def event_type(self) -> str:
        """
        Returns the type of the event.
        """
        ...
