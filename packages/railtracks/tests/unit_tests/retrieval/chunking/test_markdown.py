"""Tests for MarkdownHeaderChunker."""

from __future__ import annotations

import pytest

from railtracks.retrieval import Document
from railtracks.retrieval.chunking import MarkdownHeaderChunker


def test_checklist(chunker_checklist, markdown_doc, short_doc, empty_doc):
    # Reuse the checklist with the markdown fixture as the "multi-paragraph"
    # document — the checklist only cares that it produces multiple chunks.
    chunker_checklist(
        lambda: MarkdownHeaderChunker(),
        markdown_doc,
        short_doc,
        empty_doc,
    )


def test_header_breadcrumb(markdown_doc):
    chunker = MarkdownHeaderChunker()
    chunks = chunker.chunk(markdown_doc)

    # Find the chunk under "## Background" -> "### History"
    history_chunks = [c for c in chunks if c.metadata.get("section") == "### History"]
    assert history_chunks, "expected a chunk for the ### History section"
    assert history_chunks[0].metadata["headers"] == ["# Title", "## Background", "### History"]


def test_offsets_slice_back(markdown_doc):
    chunker = MarkdownHeaderChunker()
    chunks = chunker.chunk(markdown_doc)
    for c in chunks:
        s, e = c.offsets
        assert markdown_doc.content[s:e] == c.content


def test_preamble_has_empty_header_breadcrumb(markdown_doc):
    chunker = MarkdownHeaderChunker()
    chunks = chunker.chunk(markdown_doc)
    # The fixture has a preamble section only if one exists; for this
    # fixture there is none (first line is "# Title"). A version without
    # a leading heading should produce a chunk with headers=[].
    doc = Document(
        content="preamble text\nmore preamble\n\n# Heading\nbody",
        type="text/markdown",
    )
    chunks = chunker.chunk(doc)
    assert chunks[0].metadata["headers"] == []
    assert chunks[0].metadata["section"] is None
    assert chunks[1].metadata["section"] == "# Heading"


def test_fallback_splitter_invoked_on_oversize_section():
    text = "# Big\n" + ("word " * 400) + "\n"
    doc = Document(content=text, type="text/markdown")
    chunker = MarkdownHeaderChunker(chunk_size=200)
    chunks = chunker.chunk(doc)
    assert len(chunks) > 1
    assert all(c.metadata["section"] == "# Big" for c in chunks)
    for c in chunks:
        s, e = c.offsets
        assert doc.content[s:e] == c.content


def test_rejects_invalid_header_specifiers():
    with pytest.raises(ValueError):
        MarkdownHeaderChunker(headers_to_split_on=["-"])
    with pytest.raises(ValueError):
        MarkdownHeaderChunker(headers_to_split_on=[""])
    with pytest.raises(ValueError):
        MarkdownHeaderChunker(chunk_size=0)
