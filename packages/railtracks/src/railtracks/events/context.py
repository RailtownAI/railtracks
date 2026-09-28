from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from railtracks.context.central import external_context
from railtracks.context.scope_link import ScopeLink
from railtracks.context.session_context import ScopeEntry
from railtracks.observability import configure
from railtracks.observability.writers.jsonl._serialize import RTObserverEncoder
from railtracks.utils.logging.create import get_rt_logger

from ._base import (
    LLMAndMiddlewareSpatialParent,
    NodeAndMiddlewareSpatialParent,
    NodeSpatialParent,
    NoSpatialParent,
    SessionEventBase,
)
from ._resolve import context_spatial_parent
from .send import emit, emit_nowait

logger = get_rt_logger(__name__)

MAX_VALUE_BYTES = 16 * 1024


@dataclass(kw_only=True)
class ContextSnapshotBase(SessionEventBase[NoSpatialParent]):
    """Every key and value in the context at a session boundary."""

    values: dict[str, Any]

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
    ]
):
    def _get_spatial_parent(self, scope: ScopeLink[ScopeEntry] | None):
        return context_spatial_parent(scope)


@dataclass(kw_only=True)
class ContextGet(ContextOperationBase):
    """A `rt.context.get` and the value it returned."""

    key: str
    value: Any

    def event_type(self) -> str:
        return "context.get"


@dataclass(kw_only=True)
class ContextPut(ContextOperationBase):
    key: str
    value: Any

    def event_type(self) -> str:
        return "context.put"


@dataclass(kw_only=True)
class ContextUpdate(ContextOperationBase):
    values: dict[str, Any]

    def event_type(self) -> str:
        return "context.update"


@dataclass(kw_only=True)
class ContextDelete(ContextOperationBase):
    key: str

    def event_type(self) -> str:
        return "context.delete"


def _snapshot(value: Any) -> Any:
    """`value` as plain JSON data, taken now so later in-place edits don't reach the log."""
    try:
        encoded = json.dumps(value, cls=RTObserverEncoder)
    except Exception:
        return f"<unserializable {type(value).__name__}>"

    if len(encoded) > MAX_VALUE_BYTES:
        return f"<truncated {type(value).__name__}, {len(encoded)} bytes>"

    return json.loads(encoded)


def snapshot_mapping(values: Mapping[str, Any]) -> dict[str, Any]:
    return {key: _snapshot(value) for key, value in values.items()}


def _observing() -> bool:
    return configure.observer.loop is not None


async def emit_snapshot(event_cls: type[ContextSnapshotBase]) -> None:
    """Emit a whole-context snapshot, swallowing any failure to take it."""
    try:
        values = snapshot_mapping(dict(external_context().items()))
    except Exception:  # noqa: BLE001 - observability must not crash a run
        logger.exception("observability: failed to snapshot for %s", event_cls.__name__)
        return

    await emit(event_cls(values=values))


def record_get(key: str, value: Any) -> None:
    if _observing():
        emit_nowait(ContextGet(key=key, value=_snapshot(value)))


def record_put(key: str, value: Any) -> None:
    if _observing():
        emit_nowait(ContextPut(key=key, value=_snapshot(value)))


def record_update(values: Mapping[str, Any]) -> None:
    if _observing():
        emit_nowait(ContextUpdate(values=snapshot_mapping(values)))


def record_delete(key: str) -> None:
    if _observing():
        emit_nowait(ContextDelete(key=key))
