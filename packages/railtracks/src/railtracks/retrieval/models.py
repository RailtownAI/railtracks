from __future__ import annotations

from uuid import UUID, uuid4
from dataclasses import dataclass, field
from typing import Any



@dataclass
class Document:
    """A single piece of source content produced by a loader.

    Attributes:
        content: The raw text content.
        id: Unique identifier, auto-generated as a UUID if not provided.
        source: Origin of the content — file path, URL, database key, etc.
        metadata: Arbitrary key-value pairs attached by the loader (page number,
            language, author, etc.).
    """

    content: str
    type: str
    id: UUID = field(default_factory=uuid4)
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Chunk:
    """A contiguous slice of a Document produced by a chunker.

    Carries full lineage back to the parent Document via ``document_id``
    and preserves its position in the original text via ``index``.

    Attributes:
        content: The chunk text.
        document_id: ID of the parent ``Document``.
        id: Unique identifier, auto-generated as a UUID if not provided.
        index: Zero-based position of this chunk within the parent document.
        metadata: Merged from the parent Document's metadata by the chunker; may
            be extended with chunk-specific fields (e.g. ``token_count``).
    """

    content: str
    document_id: UUID
    id: UUID = field(default_factory=uuid4)
    index: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
