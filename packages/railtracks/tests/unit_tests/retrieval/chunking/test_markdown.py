"""Tests for MarkdownHeaderChunker."""

from __future__ import annotations

import asyncio

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
        type="markdown",
    )
    chunks = chunker.chunk(doc)
    assert chunks[0].metadata["headers"] == []
    assert chunks[0].metadata["section"] is None
    assert chunks[1].metadata["section"] == "# Heading"


def test_fallback_splitter_invoked_on_oversize_section():
    text = "# Big\n" + ("word " * 400) + "\n"
    doc = Document(content=text, type="markdown")
    chunker = MarkdownHeaderChunker(chunk_size=200)
    chunks = chunker.chunk(doc)
    assert len(chunks) > 1
    assert all(c.metadata["section"] == "# Big" for c in chunks)
    for c in chunks:
        s, e = c.offsets
        assert doc.content[s:e] == c.content


def test_body_has_no_surrounding_whitespace():
    """Section bodies must be stripped of leading/trailing whitespace.

    The header line's trailing ``\\n`` and the blank line(s) separating
    sections are boundary markers, not content. Stripping them matches
    LangChain ``MarkdownHeaderTextSplitter`` behaviour and produces
    cleaner input for embedders.
    """
    md = (
        "# Title\n"
        "\n"
        "Intro paragraph. Second sentence.\n"
        "\n"
        "## Section\n"
        "\n"
        "Body text here.\n"
        "\n"
    )
    doc = Document(content=md, type="markdown")
    chunks = MarkdownHeaderChunker().chunk(doc)
    for c in chunks:
        assert c.content == c.content.strip(), (
            f"chunk under {c.metadata.get('section')!r} has surrounding whitespace: "
            f"{c.content!r}"
        )


def test_body_offsets_match_stripped_content():
    """doc.content[start:end] must equal the stripped body exactly."""
    md = (
        "# Intro\n\nFirst paragraph.\n\n"
        "## Details\n\nSecond paragraph.\n\n"
    )
    doc = Document(content=md, type="markdown")
    chunks = MarkdownHeaderChunker().chunk(doc)
    assert len(chunks) == 2
    for c in chunks:
        s, e = c.offsets
        assert doc.content[s:e] == c.content
    # Exact content (no leading \n, no trailing \n\n)
    assert chunks[0].content == "First paragraph."
    assert chunks[1].content == "Second paragraph."


def test_rejects_invalid_header_specifiers():
    with pytest.raises(ValueError):
        MarkdownHeaderChunker(headers_to_split_on=["-"])
    with pytest.raises(ValueError):
        MarkdownHeaderChunker(headers_to_split_on=[""])
    with pytest.raises(ValueError):
        MarkdownHeaderChunker(chunk_size=0)


# -------------------------------------------------------------------
# Async: achunk parity
# -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_achunk_matches_sync_chunk(markdown_doc):
    chunker = MarkdownHeaderChunker()
    sync_chunks = chunker.chunk(markdown_doc)
    async_chunks = await chunker.achunk(markdown_doc)

    assert len(async_chunks) == len(sync_chunks)
    for sc, ac in zip(sync_chunks, async_chunks):
        assert sc.content == ac.content
        assert sc.offsets == ac.offsets
        assert sc.metadata["headers"] == ac.metadata["headers"]
        assert sc.metadata["section"] == ac.metadata["section"]


@pytest.mark.asyncio
async def test_achunk_empty_document(empty_doc):
    chunker = MarkdownHeaderChunker()
    assert await chunker.achunk(empty_doc) == []


@pytest.mark.asyncio
async def test_concurrent_achunk():
    chunker = MarkdownHeaderChunker()
    docs = [
        Document(
            content=f"# Doc {i}\nIntro.\n\n## Section\nBody text.\n",
            type="markdown",
        )
        for i in range(5)
    ]
    results = await asyncio.gather(*[chunker.achunk(doc) for doc in docs])
    assert len(results) == 5
    for doc, chunks in zip(docs, results):
        assert all(c.document_id == doc.id for c in chunks)
