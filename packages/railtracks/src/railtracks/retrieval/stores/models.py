from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from ..models import EmbeddedChunk


@dataclass(frozen=True)
class Entity:
    name: str
    type: str
    source_chunk_id: UUID
    metadata: dict = field(default_factory=dict)


# Label values every backend can store and filter on, and json.dumps can encode.
_LABEL_VALUE_TYPES = (str, int, float, bool)


@dataclass(frozen=True)
class StoreScope:
    """Equality-filter namespace for store entries.

    Each entry in ``labels`` becomes a mandatory equality filter on every
    write and read. The retrieval module is agnostic about what dimensions
    you scope by — pick whichever axes fit your tenancy model::

        StoreScope(labels={"user_id": "alice"})  # SaaS tenancy
        StoreScope(labels={"organization": "acme", "environment": "prod"})  # B2B
        StoreScope(labels={"agent_id": "docs-bot", "session_id": "s1"})  # agent context
        StoreScope(labels={"account_id": 42, "is_prod": True})  # non-string scalars

    Scopes match exactly: ``{"tenant": "alice"}`` does not match an entry
    written with ``{"tenant": "alice", "env": "prod"}``. An empty scope is the
    same as no scope (``None``) and matches only unscoped entries. To search
    across every scope, pass :data:`ALL_SCOPES` instead.

    The ``scope_`` prefix applied in :meth:`to_payload_filters` avoids key
    collisions in flat payload dicts that also carry content fields.

    Raises:
        TypeError: If a label key isn't a ``str`` or a label value isn't a
            ``str``, ``int``, ``float`` or ``bool``. Convert other ids (such
            as a ``UUID``) with ``str(value)`` first.
    """

    labels: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for key, value in self.labels.items():
            if not isinstance(key, str):
                raise TypeError(
                    f"StoreScope label keys must be str, got {key!r} "
                    f"({type(key).__name__})."
                )
            if not isinstance(value, _LABEL_VALUE_TYPES):
                raise TypeError(
                    f"StoreScope label {key!r} is a {type(value).__name__}; "
                    "label values must be str, int, float or bool. Convert it "
                    "first, e.g. str(value)."
                )

    def to_payload_filters(self) -> dict[str, Any]:
        return {f"scope_{k}": v for k, v in self.labels.items()}

    def to_key(self) -> str:
        """Canonical string for this exact label set, independent of label order."""
        return json.dumps(dict(self.labels), sort_keys=True, separators=(",", ":"))


class AllScopes(Enum):
    """Type of :data:`ALL_SCOPES`."""

    ALL_SCOPES = "all_scopes"


ALL_SCOPES = AllScopes.ALL_SCOPES
"""Searches every scope when passed as a read's ``scope``. Writes and deletes
don't accept it; use ``Store.delete_where`` to delete across scopes."""

# Payload key holding StoreScope.to_key(), so filters can match a scope exactly.
SCOPE_KEY = "scope"


def exact_scope_filter(scope: StoreScope | None) -> dict[str, str]:
    """Equality filter matching entries written with exactly ``scope``.

    ``None`` and an empty ``StoreScope`` both match only unscoped entries.

    Raises:
        ValueError: If ``scope`` is ``ALL_SCOPES``, which only reads accept.
    """
    if isinstance(scope, AllScopes):
        raise ValueError(
            "ALL_SCOPES is only valid for reads; use Store.delete_where to act "
            "across every scope."
        )
    return {SCOPE_KEY: (scope if scope is not None else StoreScope()).to_key()}


@dataclass
class StoreEntry:
    # Required fields
    id: UUID
    content: str
    vector: list[float] | None
    embedding_model: str
    chunk_id: UUID
    document_id: UUID
    # Optional enrichment fields
    abstract: str | None = None
    summary: str | None = None
    scope: StoreScope | None = None
    # Optional chunk provenance
    chunk_index: int = 0
    parent_chunk_id: UUID | None = None
    chunk_offsets: tuple[int, int] | None = None
    chunk_metadata: dict = field(default_factory=dict)
    # Optional embedding provenance
    embedding_version: str | None = None
    # Optional store metadata
    entities: list[Entity] | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))

    @classmethod
    def from_chunk(
        cls,
        embedded_chunk: EmbeddedChunk,
        *,
        scope: StoreScope | None = None,
        abstract: str | None = None,
        summary: str | None = None,
        entities: list[Entity] | None = None,
        valid_from: datetime | None = None,
        valid_until: datetime | None = None,
    ) -> StoreEntry:
        chunk = embedded_chunk.chunk
        return cls(
            id=chunk.id,
            content=chunk.content,
            vector=embedded_chunk.vector,
            embedding_model=embedded_chunk.embedding_model,
            embedding_version=embedded_chunk.embedding_version,
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            chunk_index=chunk.index,
            parent_chunk_id=chunk.parent_chunk_id,
            chunk_offsets=chunk.offsets,
            chunk_metadata=chunk.metadata,
            scope=scope,
            abstract=abstract,
            summary=summary,
            entities=entities,
            valid_from=valid_from,
            valid_until=valid_until,
        )


@dataclass
class RetrievedStoreEntry:
    entry: StoreEntry
    score: float
    rank: int
    source_retriever: str | None = None
    rerank_score: float | None = None


@dataclass
class StoreQuery:
    text: str
    scope: StoreScope | AllScopes | None = None
    embedding: list[float] | None = None
    top_k: int = 10
    metadata_filters: dict[str, Any] | None = None
