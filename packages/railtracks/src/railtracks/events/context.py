from __future__ import annotations

import json
import os
import warnings
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Mapping

from typing_extensions import Self

from railtracks.context.central import safe_get_runner_context
from railtracks.context.scope_link import ScopeLink
from railtracks.context.session_context import ScopeEntry
from railtracks.observability import configure
from railtracks.observability.writers.jsonl._serialize import RTObserverEncoder
from railtracks.utils.logging.create import get_rt_logger

# module import, not the name: _resolve -> railtracks.context -> here is a cycle,
# so _resolve may still be loading when this module is first imported
from . import _resolve
from ._base import (
    LLMAndMiddlewareSpatialParent,
    NodeAndMiddlewareSpatialParent,
    NodeSpatialParent,
    NoSpatialParent,
    SessionEventBase,
)
from .send import emit, emit_nowait

logger = get_rt_logger(__name__)


class ContextEventsLevel(IntEnum):
    """What `rt.context` calls record, set as 0, 1 or 2 in RAILTRACKS_CONTEXT_EVENTS."""

    OFF = 0
    KEYS = 1
    KEYS_AND_VALUES = 2


def _context_events_level() -> ContextEventsLevel:
    """Parse RAILTRACKS_CONTEXT_EVENTS. Unset means KEYS_AND_VALUES, and so does anything
    other than 0, 1 or 2, with a warning."""
    raw = os.environ.get("RAILTRACKS_CONTEXT_EVENTS", "").strip()
    if not raw:
        return ContextEventsLevel.KEYS_AND_VALUES

    if raw in ("0", "1", "2"):
        return ContextEventsLevel(int(raw))

    warnings.warn(
        f"RAILTRACKS_CONTEXT_EVENTS={raw!r} is not 0, 1 or 2; recording keys and values.",
        stacklevel=2,
    )
    return ContextEventsLevel.KEYS_AND_VALUES


def _snapshot(value: Any) -> Any:
    """`value` as plain JSON data, taken now so later in-place edits don't reach the log."""
    try:
        return json.loads(json.dumps(value, cls=RTObserverEncoder))
    except Exception:
        return f"<unserializable {type(value).__name__}>"


@dataclass(kw_only=True)
class KeysAndValuesMixin:
    keys: list[str]
    values: dict[str, Any] | None

    @classmethod
    def from_mapping(
        cls, mapping: Mapping[str, Any], at: ContextEventsLevel, **kwargs
    ) -> Self:
        values = None
        if at == ContextEventsLevel.KEYS_AND_VALUES:
            values = {key: _snapshot(value) for key, value in mapping.items()}
        return cls(keys=list(mapping), values=values, **kwargs)


@dataclass(kw_only=True)
class ContextSnapshotBase(SessionEventBase[NoSpatialParent], KeysAndValuesMixin):
    """Every key in the context at a session boundary, and the values when `level` records
    them."""

    level: int

    def _get_spatial_parent(self, scope: ScopeLink[ScopeEntry] | None):
        return NoSpatialParent()


@dataclass(kw_only=True)
class ContextCreation(ContextSnapshotBase):
    """The context as the run starts."""

    def event_type(self) -> str:
        return "context.creation"


@dataclass(kw_only=True)
class ContextCompletion(ContextSnapshotBase):
    """The context as the run ends."""

    def event_type(self) -> str:
        return "context.completion"


@dataclass(kw_only=True)
class ContextOperationBase(
    SessionEventBase[
        NodeAndMiddlewareSpatialParent
        | LLMAndMiddlewareSpatialParent
        | NodeSpatialParent
    ],
    KeysAndValuesMixin,
):
    def _get_spatial_parent(self, scope: ScopeLink[ScopeEntry] | None):
        return _resolve.context_spatial_parent(scope)


@dataclass(kw_only=True)
class ContextGet(ContextOperationBase):
    """A `rt.context.get` and the value it returned."""

    def event_type(self) -> str:
        return "context.get"


@dataclass(kw_only=True)
class ContextPut(ContextOperationBase):
    def event_type(self) -> str:
        return "context.put"


@dataclass(kw_only=True)
class ContextUpdate(ContextOperationBase):
    def event_type(self) -> str:
        return "context.update"


@dataclass(kw_only=True)
class ContextDelete(ContextOperationBase):
    def event_type(self) -> str:
        return "context.delete"


def _recording_level() -> ContextEventsLevel:
    if not configure.observer.is_observing:
        return ContextEventsLevel.OFF
    return _context_events_level()


async def emit_snapshot(event_cls: type[ContextSnapshotBase]) -> None:
    """Emit a whole-context snapshot, swallowing any failure to take it."""
    level = _recording_level()
    if level == ContextEventsLevel.OFF:
        return

    try:
        context = safe_get_runner_context()
        store = dict(context.external_context.items())
        event = event_cls.from_mapping(store, at=level, level=int(level))
    except Exception:  # noqa: BLE001 - observability must not crash a run
        logger.exception("observability: failed to snapshot for %s", event_cls.__name__)
        return

    await emit(event)


def record_get(key: str, value: Any) -> None:
    level = _recording_level()
    if level != ContextEventsLevel.OFF:
        emit_nowait(ContextGet.from_mapping({key: value}, at=level))


def record_put(key: str, value: Any) -> None:
    level = _recording_level()
    if level != ContextEventsLevel.OFF:
        emit_nowait(ContextPut.from_mapping({key: value}, at=level))


def record_update(values: Mapping[str, Any]) -> None:
    level = _recording_level()
    if level != ContextEventsLevel.OFF:
        emit_nowait(ContextUpdate.from_mapping(values, at=level))


def record_delete(key: str) -> None:
    if _recording_level() != ContextEventsLevel.OFF:
        emit_nowait(ContextDelete(keys=[key], values=None))
