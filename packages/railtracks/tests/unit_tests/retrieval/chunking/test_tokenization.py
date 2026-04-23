"""Tokenizer protocol + TiktokenTokenizer."""

from __future__ import annotations

from railtracks.retrieval.chunking import TiktokenTokenizer, Tokenizer


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
