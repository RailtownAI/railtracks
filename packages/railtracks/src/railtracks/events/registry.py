"""Event registry, the source of truth for what payload columns each namespace exposes.

``payload_columns(namespace)`` returns ``{payload_key: ColumnKind}`` for every event
class in the namespace, unioned. Storage-layer mapping lives
in the consumer leaving this module agnostic.
"""

from __future__ import annotations

import datetime
import types
from dataclasses import dataclass, fields
from enum import Enum
from typing import Any, Literal, Union, get_args, get_origin, get_type_hints

# Unconditional imports so ``get_type_hints`` on middleware event classes can resolve
from railtracks.guardrails.core.decision import GuardrailDecision
from railtracks.llm.history import MessageHistory
from railtracks.llm.message import Message
from railtracks.llm.response import Response
from railtracks.llm.tools.tool import Tool

from ._base import Parent, SessionEventBase, SpatialParent, Unset
from .llm import (
    LLMCreationEvent,
    LLMFailureEvent,
    LLMInvocationEvent,
    LLMResponseEvent,
)
from .middleware import (
    MiddlewareCreationEvent,
    MiddlewareFailureEvent,
    MiddlewareGuardInputFailureEvent,
    MiddlewareGuardInputInvocationEvent,
    MiddlewareGuardInputResponseEvent,
    MiddlewareGuardOutputFailureEvent,
    MiddlewareGuardOutputInvocationEvent,
    MiddlewareGuardOutputResponseEvent,
    MiddlewareInvocationEvent,
    MiddlewareModelFailureEvent,
    MiddlewareModelInputInvocationEvent,
    MiddlewareModelInputResponseEvent,
    MiddlewareModelInvocationEvent,
    MiddlewareModelOutputFailureEvent,
    MiddlewareModelOutputInvocationEvent,
    MiddlewareModelOutputResponseEvent,
    MiddlewareModelResponseEvent,
    MiddlewareOutputFailureEvent,
    MiddlewareOutputInvocationEvent,
    MiddlewareOutputResponseEvent,
    MiddlewareResponseEvent,
)
from .node import (
    NodeCreation,
    NodeDestruction,
    NodeFailure,
    NodeInvocation,
    NodeResponse,
)
from .session import (
    SessionCompleted,
    SessionStarted,
)

EVENT_CLASSES: list[type[SessionEventBase]] = [
    LLMCreationEvent,
    LLMInvocationEvent,
    LLMResponseEvent,
    LLMFailureEvent,
    NodeCreation,
    NodeInvocation,
    NodeResponse,
    NodeFailure,
    NodeDestruction,
    MiddlewareCreationEvent,
    MiddlewareInvocationEvent,
    MiddlewareResponseEvent,
    MiddlewareFailureEvent,
    MiddlewareModelInvocationEvent,
    MiddlewareModelResponseEvent,
    MiddlewareModelFailureEvent,
    MiddlewareModelInputInvocationEvent,
    MiddlewareModelInputResponseEvent,
    MiddlewareModelOutputInvocationEvent,
    MiddlewareModelOutputResponseEvent,
    MiddlewareModelOutputFailureEvent,
    MiddlewareOutputInvocationEvent,
    MiddlewareOutputResponseEvent,
    MiddlewareOutputFailureEvent,
    MiddlewareGuardInputInvocationEvent,
    MiddlewareGuardInputResponseEvent,
    MiddlewareGuardInputFailureEvent,
    MiddlewareGuardOutputInvocationEvent,
    MiddlewareGuardOutputResponseEvent,
    MiddlewareGuardOutputFailureEvent,
    SessionStarted,
    SessionCompleted,
]

class ColumnKind(str, Enum):
    """DB-agnostic description of a payload column's value type.

    Storage layers translate this to a concrete column type (DuckDB VARCHAR,
    Parquet UTF8, Postgres TEXT, …). Kept as a ``str`` enum so it serializes
    cleanly if anyone needs to hand it across a boundary.

    ``ENUM`` is always paired with ``ColumnSpec.enum_members`` — the closed set
    of allowed string values. Other kinds have ``enum_members = None``.
    """

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    TIMESTAMP_TZ = "timestamp_tz"
    JSON = "json"
    ENUM = "enum"


@dataclass(frozen=True)
class ColumnSpec:
    """A single payload column's kind plus, for ``ENUM`` columns, its allowed values."""

    kind: ColumnKind
    enum_members: tuple[str, ...] | None = None


_TYPE_LOCALS: dict[str, Any] = {
    "MessageHistory": MessageHistory,
    "Message": Message,
    "Response": Response,
    "Tool": Tool,
    "GuardrailDecision": GuardrailDecision,
}

_SCALAR_KINDS: dict[type, ColumnKind] = {
    str: ColumnKind.STRING,
    int: ColumnKind.INTEGER,
    float: ColumnKind.FLOAT,
    bool: ColumnKind.BOOLEAN,
    datetime.datetime: ColumnKind.TIMESTAMP_TZ,
}

# Fields on ``SessionEventBase`` / ``ParentEventBase`` that carry a TypeVar-typed
# ``SpatialParent`` / ``Parent`` value. TypeVars don't resolve through ``get_type_hints``,
# so we key on field name and flatten across the full union of subtypes below.
_TAGGED_UNION_FIELDS: dict[str, type] = {
    "spatial_parent": SpatialParent,
    "parent": Parent,
}


def _namespace_of(cls: type[SessionEventBase]) -> str:
    """Return the leading segment of ``event_type()`` for ``cls``."""
    instance = cls.__new__(cls)
    return instance.event_type().split(".", 1)[0]


def _is_union(origin: Any) -> bool:
    """Return True if ``origin`` is a ``Union`` type.
    Python 3.10+ has ``types.UnionType`` for the ``|`` operator, 
    but ``typing.Union`` is still used for ``Union[...]``.
    """
    return origin is Union or origin is types.UnionType


def _unwrap(annotation: Any) -> Any:
    """Strip ``None`` and the ``Unset`` flags from a union annotation."""
    if not _is_union(get_origin(annotation)):
        return annotation
    args = tuple(a for a in get_args(annotation) if a is not type(None) and a is not Unset)
    if len(args) == 1:
        return args[0]
    if not args:
        return annotation
    return Union[args]


def _annotation_to_spec(annotation: Any) -> ColumnSpec:
    """Map a Python annotation to a ``ColumnSpec``.

    ``Literal`` of str-Enum members or bare strings → ``ENUM`` with those values as
    members. Falls back to ``JSON`` for anything structured (dataclasses, Pydantic
    models, ``list``/``dict``/``tuple``, ``Any``, enums, ``type[BaseModel]``, etc).
    """
    annotation = _unwrap(annotation)

    if get_origin(annotation) is Literal:
        literal_args = get_args(annotation)
        # ``bool`` before ``int`` — bool subclasses int in Python.
        if all(isinstance(a, bool) for a in literal_args):
            return ColumnSpec(kind=ColumnKind.BOOLEAN)
        if all(isinstance(a, int) for a in literal_args):
            return ColumnSpec(kind=ColumnKind.INTEGER)
        if all(isinstance(a, str) for a in literal_args):
            # ``str, Enum`` members subclass ``str`` but ``str(member)`` isn't
            # guaranteed to return the value on older Python, so normalize.
            members = tuple(
                a.value if isinstance(a, Enum) else a for a in literal_args
            )
            return ColumnSpec(kind=ColumnKind.ENUM, enum_members=members)
        return ColumnSpec(kind=ColumnKind.JSON)

    if annotation in _SCALAR_KINDS:
        return ColumnSpec(kind=_SCALAR_KINDS[annotation])

    return ColumnSpec(kind=ColumnKind.JSON)


def _merge_specs(existing: ColumnSpec, new: ColumnSpec, *, column: str, context: str) -> ColumnSpec:
    """Combine two specs for the same column across sibling classes.

    Same-kind non-ENUM specs just re-use ``existing``. ENUM specs union their
    member sets. Conflicting kinds raise.
    """
    if existing.kind != new.kind:
        raise ValueError(
            f"Kind conflict in {context}: "
            f"{column} declared as both {existing.kind.value} and {new.kind.value}"
        )
    if existing.kind is ColumnKind.ENUM:
        merged = tuple(
            sorted(set(existing.enum_members or ()) | set(new.enum_members or ()))
        )
        return ColumnSpec(kind=ColumnKind.ENUM, enum_members=merged)
    return existing


def _flatten_tagged_union(prefix: str, base: type) -> dict[str, ColumnSpec]:
    """Union of ``{prefix}_{subfield}`` columns across every concrete subclass of ``base``.

    On-write the payload gets each ``SpatialParent`` / ``Parent`` field emitted as
    ``<prefix>_<subfield>``. A given event only produces the subset matching its own
    subtype; the missing keys become SQL NULL at read time.

    For ``ENUM`` discriminator subfields (e.g. ``spatial_type``), members are unioned
    across every subtype so the column's ENUM covers every possible value.
    """
    columns: dict[str, ColumnSpec] = {}
    for subclass in _all_subclasses(base):
        hints = get_type_hints(subclass, localns=_TYPE_LOCALS, include_extras=False)
        for f in fields(subclass):
            col = f"{prefix}_{f.name}"
            spec = _annotation_to_spec(hints.get(f.name, f.type))
            existing = columns.get(col)
            if existing is None:
                columns[col] = spec
            else:
                columns[col] = _merge_specs(
                    existing, spec, column=col, context=f"flattening {base.__name__}"
                )
    return columns


def _all_subclasses(base: type) -> list[type]:
    """Return a list of every concrete subclass of ``base``, recursively."""
    seen: list[type] = []
    for sub in base.__subclasses__():
        seen.append(sub)
        seen.extend(_all_subclasses(sub))
    return seen


def payload_columns(namespace: str) -> dict[str, ColumnSpec]:
    """Union of ``{payload_key: ColumnSpec}`` across every event class in ``namespace``.

    ENUM members are unioned across event classes so a namespace-level discriminator
    (e.g. ``spatial_parent_spatial_type``) covers every possible value. Unknown
    namespaces return ``{}``.
    """
    columns: dict[str, ColumnSpec] = {}
    for cls in EVENT_CLASSES:
        if _namespace_of(cls) != namespace:
            continue
        hints = get_type_hints(cls, localns=_TYPE_LOCALS, include_extras=False)
        for f in fields(cls):
            if f.name in _TAGGED_UNION_FIELDS:
                new_cols = _flatten_tagged_union(f.name, _TAGGED_UNION_FIELDS[f.name])
            else:
                new_cols = {f.name: _annotation_to_spec(hints.get(f.name, f.type))}

            for col, spec in new_cols.items():
                existing = columns.get(col)
                if existing is None:
                    columns[col] = spec
                else:
                    columns[col] = _merge_specs(
                        existing, spec, column=col, context=f"namespace {namespace!r}"
                    )

    return columns


def namespaces() -> list[str]:
    """Sorted, de-duplicated list of every namespace in the registry."""
    return sorted({_namespace_of(cls) for cls in EVENT_CLASSES})
