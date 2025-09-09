# tests/conftest.py

import pytest
import itertools

_uuid_counter = itertools.count()

class DummyEmbeddingService:
    def embed(self, texts):
        # If input is str, return 1D vector;
        # If input is list, return 2D list of vectors!
        if isinstance(texts, str):
            return [float(sum(ord(c) for c in texts) % 10) for _ in range(3)]
        return [[float(sum(ord(c) for c in t) % 10) for _ in range(3)] for t in texts]

class DummyRecord:
    def __init__(self, id, vector, text="", metadata=None):
        self.id = id
        self.vector = vector
        self.text = text
        self.metadata = metadata or {}

class DummySearchEntry:
    def __init__(self, score, record):
        self.score = score
        self.record = record

class DummyMetric:
    cosine = "cosine"
    l2 = "l2"
    dot = "dot"
    def __init__(self, val): self.value = val

class DummyTextChunkingService:
    def __init__(self, **kwargs): pass
    def chunk(self, content):
        return [content[:len(content)//2], content[len(content)//2:]]
    @staticmethod
    def chunk_by_token(content):
        mid = len(content)//2
        return [content[:mid], content[mid:]]

class DummyVectorRecord:
    def __init__(self, id, vector, text, metadata):
        self.id = id
        self.vector = vector
        self.text = text
        self.metadata = metadata

class DummyTextObject:
    def __init__(self, raw_content, embeddings=None, path=None):
        self.raw_content = raw_content
        self.chunked_content = None
        self.embeddings = None
        self.hash = "hash123"
        self.path = path
    def set_chunked(self, chunks):
        self.chunked_content = chunks
    def set_embeddings(self, embeddings):
        self.embeddings = embeddings
    def get_metadata(self):
        return {"meta": "info", "source": self.path or "memory"}

@pytest.fixture
def dummy_embedding_service():
    return DummyEmbeddingService

@pytest.fixture
def dummy_record():
    return DummyRecord

@pytest.fixture
def dummy_search_result():
    return DummySearchEntry

@pytest.fixture
def dummy_metric():
    return DummyMetric

@pytest.fixture
def dummy_text_chunking_service():
    return DummyTextChunkingService

@pytest.fixture
def dummy_vector_record():
    return DummyVectorRecord

@pytest.fixture
def dummy_text_object():
    return DummyTextObject