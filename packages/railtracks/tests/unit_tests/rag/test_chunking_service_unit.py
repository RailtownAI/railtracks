import pytest
from railtracks.rag.chunking_service import (
    BaseChunkingService,
    TextChunkingService,
)
from railtracks.rag import chunking_service

# -- Import module and patch DummyTokenizer using monkeypatch fixture --
@pytest.fixture(autouse=True)
def patch_tokenizer(monkeypatch):

    class DummyTokenizer:
        def __init__(self, model):
            self.model = model
        def encode(self, s):
            return [ord(c) for c in s]
        def decode(self, tokens):
            return ''.join(chr(t) for t in tokens)

    monkeypatch.setattr(chunking_service, "Tokenizer", DummyTokenizer)

def test_base_chunking_set_and_call():
    called = {}
    class DummyBase(BaseChunkingService):
        def dummy_strategy(self, content, *a, **k):
            called["ran"] = content
            return "done"

    s = DummyBase(strategy=DummyBase.dummy_strategy)
    assert callable(s.strategy)
    assert s.chunk("abc") == "done"
    assert called["ran"] == "abc"

    def other_strat(self, c):
        return c.upper()
    s.set_strategy(other_strat)
    assert s.chunk("hello") == "HELLO"

    s2 = DummyBase(strategy=None)
    with pytest.raises(ValueError):
        s2.chunk("abc")

def test_text_chunk_by_char_simple():
    s = TextChunkingService(chunk_size=5, chunk_overlap=2)
    text = "abcdefghij"
    chunks = s.chunk_by_char(text)
    assert chunks == ["abcde", "defgh", "ghij", "j"]

def test_text_chunk_by_char_exact_end():
    s = TextChunkingService(chunk_size=4, chunk_overlap=1)
    text = "abcdefg"
    chunks = s.chunk_by_char(text)
    assert chunks == ["abcd", "defg", "g"]

def test_text_chunk_by_token_basic():
    s = TextChunkingService(chunk_size=3, chunk_overlap=1, model="mymodel")
    text = "abcde"
    chunks = s.chunk_by_token(text)
    assert chunks == ["abc", "cde"]

def test_text_chunk_by_token_overlap_error():
    s = TextChunkingService(chunk_size=3, chunk_overlap=5, model="test")
    with pytest.raises(ValueError):
        s.chunk_by_token("abcde")

def test_text_chunk_by_token_model_none_error():
    s = TextChunkingService(chunk_size=3, chunk_overlap=1, model=None)
    with pytest.raises(ValueError):
        s.chunk_by_token("abcde")