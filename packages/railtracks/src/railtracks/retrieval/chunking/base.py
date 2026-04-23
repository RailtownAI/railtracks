"""Core abstractions for the chunking subsystem.

``Splitter`` is a structural protocol for ``str -> list[str]`` boundary
detection. ``Chunker`` is an ABC that turns a :class:`Document` into a list
of :class:`Chunk` objects while enforcing all cross-chunker invariants in
a single protected helper (``_make_chunks``).

Subclasses decide *where* to split. They never construct :class:`Chunk`
objects directly; they delegate to ``_make_chunks``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from ..models import Chunk, Document


@runtime_checkable
class Splitter(Protocol):
    """Pure ``str -> list[str]`` boundary detection.

    Splitters are reusable building blocks: a recursive splitter can be
    composed inside a markdown chunker or used directly. Splitters know
    nothing about :class:`Chunk` or :class:`Document` objects.
    """

    def split(self, text: str) -> list[str]: ...


class Chunker(ABC):
    """Splits a :class:`Document` into a list of :class:`Chunk` objects.

    Subclasses decide *where* to split. The base class guarantees:

    * ``document_id`` propagation
    * dense, 0-based ``index`` assignment
    * ``offsets`` copy-through when provided
    * ``parent_chunk_id`` propagation when provided
    * shallow-copied metadata inheritance from the source ``Document``,
      overlaid with any per-chunk ``extra_metadata``

    Subclasses must go through :meth:`_make_chunks` to assemble their
    output; this is where every invariant lives.
    """

    @abstractmethod
    def chunk(self, document: Document) -> list[Chunk]:
        """Split a :class:`Document` into a list of :class:`Chunk` objects."""

    def chunk_text(
        self,
        text: str,
        document_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        """Convenience wrapper for callers without a :class:`Document`.

        Synthesizes a transient ``Document`` with ``type="text/plain"``
        and calls :meth:`chunk`. Production callers should build and
        track their own ``Document`` objects so document-level lifecycle
        operations remain possible.

        Args:
            text: Raw text to chunk.
            document_id: Optional UUID to assign to the transient
                document. When ``None``, a fresh UUID is generated.
            metadata: Optional metadata attached to the transient
                document. Inherited (shallow-copied) onto every produced
                chunk.
        """
        kwargs: dict[str, Any] = {
            "content": text,
            "type": "text/plain",
            "metadata": dict(metadata) if metadata is not None else {},
        }
        if document_id is not None:
            kwargs["id"] = document_id
        document = Document(**kwargs)
        return self.chunk(document)

    # -----------------------------------------------------------------
    # Helpers available to subclasses; not part of the public surface.
    # -----------------------------------------------------------------

    def _make_chunks(
        self,
        document: Document,
        pieces: list[str],
        offsets: list[tuple[int, int]] | None = None,
        parent_chunk_id: UUID | None = None,
        extra_metadata: list[dict[str, Any]] | None = None,
    ) -> list[Chunk]:
        """Assemble ``Chunk`` objects from split pieces.

        This is the single place invariants are enforced. Subclasses must
        call this helper instead of constructing ``Chunk`` objects
        directly.

        Args:
            document: Source document; ``document.id`` and
                ``document.metadata`` propagate onto every produced
                chunk.
            pieces: Ordered list of chunk texts. Empty pieces are kept as
                given; callers are responsible for filtering them out if
                they want.
            offsets: Optional per-piece ``(start, end)`` character
                offsets into ``document.content``. When provided, must
                have the same length as ``pieces``.
            parent_chunk_id: Optional coarser-chunk id to attach to every
                produced chunk (for hierarchical chunking).
            extra_metadata: Optional per-piece metadata dicts, overlaid
                on top of the document's metadata. When provided, must
                have the same length as ``pieces``.

        Returns:
            List of :class:`Chunk` objects, one per piece, with
            ``index`` set densely from ``0`` to ``len(pieces) - 1``.

        Raises:
            ValueError: If ``offsets`` or ``extra_metadata`` is provided
                with a length mismatching ``pieces``.
        """
        if offsets is not None and len(offsets) != len(pieces):
            raise ValueError(
                f"offsets length ({len(offsets)}) does not match pieces length "
                f"({len(pieces)})"
            )
        if extra_metadata is not None and len(extra_metadata) != len(pieces):
            raise ValueError(
                f"extra_metadata length ({len(extra_metadata)}) does not match "
                f"pieces length ({len(pieces)})"
            )

        chunks: list[Chunk] = []
        for i, piece in enumerate(pieces):
            metadata = dict(document.metadata)
            if extra_metadata is not None:
                metadata.update(extra_metadata[i])
            chunks.append(
                Chunk(
                    content=piece,
                    document_id=document.id,
                    index=i,
                    parent_chunk_id=parent_chunk_id,
                    offsets=offsets[i] if offsets is not None else None,
                    metadata=metadata,
                )
            )
        return chunks
