"""Shared fixtures for the retrieval module test suite.

Exports:

* Four ``Document`` factory fixtures covering the cases every chunker
  must handle: empty, sub-chunk short, multi-paragraph plain text, and
  nested-header markdown.
* ``chunker_checklist``: a callable fixture every per-chunker test file
  delegates to. Centralizing it here avoids cross-package relative
  imports (the ``tests/`` tree is a namespace package without
  ``__init__.py``).
"""

from __future__ import annotations

from typing import Callable

import pytest

from railtracks.retrieval import Chunk, Document

# ---------------------------------------------------------------------------
# Document fixtures
# ---------------------------------------------------------------------------

_SHORT_TEXT = "One short line."

_MULTI_PARAGRAPH_TEXT = (
    "Paragraph one opens the document with a first sentence. "
    "It continues with a second sentence that is a bit longer.\n\n"
    "Paragraph two is a single sentence.\n\n"
    "Paragraph three is deliberately larger so that recursive chunkers "
    "have something to subdivide. It contains several sentences. Each "
    "sentence reiterates the fact that the paragraph is large. The "
    "paragraph ends here."
)

_MARKDOWN_TEXT = (
    "# Title\n"
    "Intro paragraph, no sub-header.\n\n"
    "## Background\n"
    "Background paragraph one.\n\n"
    "### History\n"
    "Some history facts. More history facts.\n\n"
    "## Motivation\n"
    "Why the work matters.\n\n"
    "# Methods\n"
    "Methods intro.\n\n"
    "## Setup\n"
    "Setup instructions.\n"
)


@pytest.fixture
def empty_doc() -> Document:
    return Document(content="", type="text", metadata={"kind": "empty"})


@pytest.fixture
def short_doc() -> Document:
    return Document(
        content=_SHORT_TEXT, type="text", metadata={"kind": "short"}
    )


@pytest.fixture
def multi_paragraph_doc() -> Document:
    return Document(
        content=_MULTI_PARAGRAPH_TEXT,
        type="text",
        metadata={"kind": "multi_paragraph", "lang": "en"},
    )


@pytest.fixture
def markdown_doc() -> Document:
    return Document(
        content=_MARKDOWN_TEXT,
        type="markdown",
        metadata={"kind": "markdown"},
    )


# ---------------------------------------------------------------------------
# Shared per-chunker checklist
# ---------------------------------------------------------------------------


def _run_checklist(
    chunker_factory: Callable[[], object],
    multi_paragraph_doc: Document,
    short_doc: Document,
    empty_doc: Document,
) -> None:
    # 1. Empty document -> no chunks
    empty_chunks = chunker_factory().chunk(empty_doc)
    assert empty_chunks == [], (
        f"expected no chunks for empty document, got {empty_chunks}"
    )

    # 2. Short (sub-chunk) document -> single chunk whose content is
    # aligned with the source (token chunkers may add leading whitespace
    # on decode, so we allow substring equivalence in either direction).
    short_chunks = chunker_factory().chunk(short_doc)
    assert len(short_chunks) == 1, (
        f"expected 1 chunk for short doc, got {len(short_chunks)}"
    )
    sc = short_chunks[0].content.strip()
    src = short_doc.content.strip()
    assert src in sc or sc in src, (
        f"short-doc chunk content {short_chunks[0].content!r} not aligned with "
        f"source {short_doc.content!r}"
    )

    # 3-6. Multi-paragraph doc
    chunks = chunker_factory().chunk(multi_paragraph_doc)
    assert len(chunks) >= 1
    assert all(isinstance(c, Chunk) for c in chunks)

    # 3. document_id propagation
    assert all(c.document_id == multi_paragraph_doc.id for c in chunks)

    # 4. dense, 0-based indices
    assert [c.index for c in chunks] == list(range(len(chunks)))

    # 5. metadata is a copy and inheritance works
    for c in chunks:
        assert c.metadata is not multi_paragraph_doc.metadata
    for c in chunks:
        for k, v in multi_paragraph_doc.metadata.items():
            assert c.metadata.get(k) == v, (
                f"expected inherited metadata {k!r}={v!r} on chunk, got "
                f"{c.metadata.get(k)!r}"
            )
    snapshot = dict(multi_paragraph_doc.metadata)
    chunks[0].metadata["_probe"] = True
    assert multi_paragraph_doc.metadata == snapshot, (
        "chunk-metadata mutation leaked into the source document"
    )
    multi_paragraph_doc.metadata["_probe_doc"] = True
    assert "_probe_doc" not in chunks[0].metadata, (
        "document-metadata mutation leaked into a previously produced chunk"
    )
    multi_paragraph_doc.metadata.pop("_probe_doc", None)

    # 6. offsets, when present, slice back to chunk content
    for c in chunks:
        if c.offsets is None:
            continue
        s, e = c.offsets
        assert 0 <= s <= e <= len(multi_paragraph_doc.content)
        assert multi_paragraph_doc.content[s:e] == c.content, (
            f"offset slice {multi_paragraph_doc.content[s:e]!r} does not match "
            f"chunk content {c.content!r}"
        )


@pytest.fixture
def chunker_checklist() -> Callable[..., None]:
    """Return the shared per-chunker checklist runner.

    Tests invoke it like::

        def test_checklist(chunker_checklist, multi_paragraph_doc, short_doc, empty_doc):
            chunker_checklist(lambda: MyChunker(...), multi_paragraph_doc, short_doc, empty_doc)
    """
    return _run_checklist
