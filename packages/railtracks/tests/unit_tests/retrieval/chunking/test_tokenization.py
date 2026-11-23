"""Tokenizer protocol + TiktokenTokenizer."""

from __future__ import annotations

import pytest
from railtracks.retrieval.chunking import TiktokenTokenizer, Tokenizer, tokenization


def test_tiktoken_tokenizer_roundtrip():
    tok = TiktokenTokenizer()
    text = "Hello world! This is a short sentence."
    tokens = tok.encode(text)
    assert isinstance(tokens, list)
    assert all(isinstance(t, int) for t in tokens)
    assert tok.decode(tokens) == text
    assert tok.count(text) == len(tokens)


def test_tiktoken_tokenizer_satisfies_protocol():
    tok = TiktokenTokenizer()
    assert isinstance(tok, Tokenizer)


def test_tiktoken_tokenizer_count_empty_string():
    tok = TiktokenTokenizer()
    assert tok.count("") == 0


def test_missing_tiktoken_hint_points_at_plain_tiktoken(monkeypatch):
    monkeypatch.setattr(tokenization, "_tiktoken", None)

    with pytest.raises(ModuleNotFoundError) as exc_info:
        tokenization.TiktokenTokenizer()

    assert "pip install tiktoken" in str(exc_info.value)
    assert "railtracks[tiktok]" not in str(exc_info.value)
