"""Tests for SemanticChunker template."""

from __future__ import annotations

import pytest

from railtracks.retrieval import Document
from railtracks.retrieval.chunking import Chunker, SemanticChunker


def _noop_embed(texts: list[str]) -> list[list[float]]:
    return [[0.0] for _ in texts]


def test_semantic_chunker_subclass_chunker_abc():
    assert isinstance(SemanticChunker(embed_fn=_noop_embed), Chunker)


def test_empty_document_returns_empty_list(empty_doc):
    assert SemanticChunker(embed_fn=_noop_embed).chunk(empty_doc) == []


def test_chunk_not_implemented():
    doc = Document(content="Some text.", type="text")
    with pytest.raises(NotImplementedError, match="SemanticChunker.chunk"):
        SemanticChunker(embed_fn=_noop_embed).chunk(doc)
