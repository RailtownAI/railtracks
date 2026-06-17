"""Tests for IdentityChunker."""

from __future__ import annotations

import pytest
from railtracks.retrieval import Document
from railtracks.retrieval.chunking import IdentityChunker


def test_checklist(chunker_checklist, multi_paragraph_doc, short_doc, empty_doc):
    chunker_checklist(lambda: IdentityChunker(), multi_paragraph_doc, short_doc, empty_doc)


def test_empty_document_returns_empty_list(empty_doc):
    assert IdentityChunker().chunk(empty_doc) == []


def test_single_chunk_returned(multi_paragraph_doc):
    chunks = IdentityChunker().chunk(multi_paragraph_doc)
    assert len(chunks) == 1


def test_chunk_content_equals_document_content(multi_paragraph_doc):
    chunks = IdentityChunker().chunk(multi_paragraph_doc)
    assert chunks[0].content == multi_paragraph_doc.content


def test_offsets_span_full_document(multi_paragraph_doc):
    chunks = IdentityChunker().chunk(multi_paragraph_doc)
    assert chunks[0].offsets == (0, len(multi_paragraph_doc.content))


def test_offsets_slice_back_to_content(multi_paragraph_doc):
    chunks = IdentityChunker().chunk(multi_paragraph_doc)
    s, e = chunks[0].offsets
    assert multi_paragraph_doc.content[s:e] == chunks[0].content


def test_document_id_propagated(multi_paragraph_doc):
    chunks = IdentityChunker().chunk(multi_paragraph_doc)
    assert chunks[0].document_id == multi_paragraph_doc.id


def test_index_is_zero(multi_paragraph_doc):
    chunks = IdentityChunker().chunk(multi_paragraph_doc)
    assert chunks[0].index == 0


def test_metadata_inherited(multi_paragraph_doc):
    chunks = IdentityChunker().chunk(multi_paragraph_doc)
    for k, v in multi_paragraph_doc.metadata.items():
        assert chunks[0].metadata[k] == v


def test_metadata_is_independent_copy(multi_paragraph_doc):
    chunks = IdentityChunker().chunk(multi_paragraph_doc)
    assert chunks[0].metadata is not multi_paragraph_doc.metadata

    snapshot = dict(multi_paragraph_doc.metadata)
    chunks[0].metadata["_probe"] = True
    assert multi_paragraph_doc.metadata == snapshot


def test_short_doc_single_chunk(short_doc):
    chunks = IdentityChunker().chunk(short_doc)
    assert len(chunks) == 1
    assert chunks[0].content == short_doc.content
    assert chunks[0].offsets == (0, len(short_doc.content))


def test_chunk_text_convenience(multi_paragraph_doc):
    chunker = IdentityChunker()
    text = multi_paragraph_doc.content
    chunks = chunker.chunk_text(text)
    assert len(chunks) == 1
    assert chunks[0].content == text


@pytest.mark.asyncio
async def test_achunk_matches_chunk(multi_paragraph_doc):
    chunker = IdentityChunker()
    sync_result = chunker.chunk(multi_paragraph_doc)
    async_result = await chunker.achunk(multi_paragraph_doc)
    assert len(async_result) == len(sync_result)
    assert async_result[0].content == sync_result[0].content
    assert async_result[0].offsets == sync_result[0].offsets
    assert async_result[0].document_id == sync_result[0].document_id


@pytest.mark.asyncio
async def test_achunk_empty_document(empty_doc):
    assert await IdentityChunker().achunk(empty_doc) == []
