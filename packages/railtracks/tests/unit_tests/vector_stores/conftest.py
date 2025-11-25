import pytest
from unittest.mock import Mock, MagicMock, patch
from railtracks.vector_stores.vector_store_base import Chunk, SearchResult, FetchResult
from railtracks.vector_stores.chroma import ChromaVectorStore


# ============================================================================
# Generic Test Data Fixtures (reusable across all vector store tests)
# ============================================================================

@pytest.fixture
def simple_vector():
    """Simple 3-dimensional vector for testing."""
    return [0.1, 0.2, 0.3]


@pytest.fixture
def short_vector():
    """Short vector for basic operations."""
    return [0.1, 0.2, 0.3, 0.4, 0.5]


@pytest.fixture
def long_vector():
    """Long vector (1000 dimensions) for testing scalability."""
    return [float(i) for i in range(1000)]


@pytest.fixture
def zero_vector():
    """Zero vector for distance tests."""
    return [0.0, 0.0, 0.0]


@pytest.fixture
def simple_metadata():
    """Simple metadata dictionary."""
    return {"key": "value"}


@pytest.fixture
def complex_metadata():
    """Complex metadata with multiple keys."""
    return {"author": "John", "date": "2024-01-01", "tags": "test,demo"}


@pytest.fixture
def custom_id():
    """Custom ID string for testing."""
    return "custom_id_123"


@pytest.fixture
def simple_content():
    """Simple content string."""
    return "Test content"


@pytest.fixture
def simple_document():
    """Simple document identifier."""
    return "test_doc.txt"


@pytest.fixture
def zero_distance():
    """Zero distance value."""
    return 0.0


@pytest.fixture
def small_distance():
    """Small distance value for similarity."""
    return 0.1


@pytest.fixture
def large_distance():
    """Large distance value for dissimilarity."""
    return 0.9


# ============================================================================
# Embedding Function Fixtures
# ============================================================================

@pytest.fixture
def mock_embedding_function():
    """Mock embedding function that returns consistent embeddings."""
    def embed(texts: list[str]) -> list[list[float]]:
        # Return embeddings with same length as input, consistent for testing
        return [[float(i) for i in range(5)] for _ in texts]
    return embed


@pytest.fixture
def mock_chroma_ephemeral_client():
    """Mock Chroma EphemeralClient."""
    client = MagicMock()
    collection = MagicMock()
    client.get_or_create_collection.return_value = collection
    return client, collection


@pytest.fixture
def mock_chroma_persistent_client():
    """Mock Chroma PersistentClient."""
    client = MagicMock()
    collection = MagicMock()
    client.get_or_create_collection.return_value = collection
    return client, collection


@pytest.fixture
def mock_chroma_http_client():
    """Mock Chroma HttpClient."""
    client = MagicMock()
    collection = MagicMock()
    client.get_or_create_collection.return_value = collection
    return client, collection


@pytest.fixture
def sample_chunk():
    """Create a sample Chunk for testing."""
    return Chunk(
        content="Test content",
        document="test_doc.txt",
        metadata={"category": "test"}
    )


@pytest.fixture
def sample_chunks():
    """Create multiple sample Chunks for testing."""
    return [
        Chunk(
            content="First test content",
            document="doc1.txt",
            metadata={"id": 1}
        ),
        Chunk(
            content="Second test content",
            document="doc2.txt",
            metadata={"id": 2}
        ),
        Chunk(
            content="Third test content",
            document="doc3.txt",
            metadata={"id": 3}
        ),
    ]


@pytest.fixture
def sample_search_results():
    """Create sample SearchResult objects."""
    return [
        SearchResult(
            id="id1",
            distance=0.1,
            content="Result 1",
            vector=[0.1, 0.2, 0.3, 0.4, 0.5],
            document="doc1.txt",
            metadata={"source": "doc1"}
        ),
        SearchResult(
            id="id2",
            distance=0.2,
            content="Result 2",
            vector=[0.2, 0.3, 0.4, 0.5, 0.6],
            document="doc2.txt",
            metadata={"source": "doc2"}
        ),
    ]


@pytest.fixture
def sample_fetch_results():
    """Create sample FetchResult objects."""
    return [
        FetchResult(
            id="id1",
            content="Fetched content 1",
            vector=[0.1, 0.2, 0.3, 0.4, 0.5],
            document="doc1.txt",
            metadata={"key": "value1"}
        ),
        FetchResult(
            id="id2",
            content="Fetched content 2",
            vector=[0.2, 0.3, 0.4, 0.5, 0.6],
            document="doc2.txt",
            metadata={"key": "value2"}
        ),
    ]


@pytest.fixture
def mock_chromadb_module():
    """Mock the chromadb module for import patching."""
    mock_chromadb = MagicMock()
    mock_chromadb.EphemeralClient = MagicMock()
    mock_chromadb.PersistentClient = MagicMock()
    mock_chromadb.HttpClient = MagicMock()
    return mock_chromadb


# ============================================================================
# Chroma Test Helpers
# ============================================================================
@pytest.fixture
def reset_chroma_class():
    def _reset_chroma_class():
        """Reset ChromaVectorStore._chroma to ensure clean initialization state.
        
        Use this in tests that call ChromaVectorStore.class_init() to ensure
        the class_init method actually runs instead of finding an existing client.
        """
        if hasattr(ChromaVectorStore, "_chroma"):
            delattr(ChromaVectorStore, "_chroma")
    
    return _reset_chroma_class


@pytest.fixture
def chroma_mocks():
    """Fixture that provides a clean ChromaVectorStore with mocked collection.
    
    Returns:
        dict: Contains 'client' (mock Chroma client) and 'collection' (mock collection)
    
    Example:
        def test_something(self, chroma_mocks):
            from railtracks.vector_stores.chroma import ChromaVectorStore
            ChromaVectorStore._chroma = chroma_mocks["client"]
            store = ChromaVectorStore(collection_name="test", ...)
    """
    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_client.get_or_create_collection.return_value = mock_collection
    return {"client": mock_client, "collection": mock_collection}


@pytest.fixture
def chroma_store(mock_embedding_function, chroma_mocks):
    """Fixture that provides a fully initialized ChromaVectorStore instance.
    
    This is the preferred way to test ChromaVectorStore methods. It gives you
    a real store instance with a mocked collection, so you only need to mock
    the specific methods you're testing.
    
    Args:
        mock_embedding_function: Fixture for embedding function
        chroma_mocks: Fixture containing mocked client and collection
    
    Returns:
        ChromaVectorStore: Fully initialized store with mocked collection
    
    Example:
        def test_upsert(self, chroma_store, chroma_mocks):
            # Store is already initialized! Just configure the mock for specific method.
            chroma_mocks["collection"].upsert.return_value = ["id1"]
            result = chroma_store.upsert("Test content")
            assert result == "id1"
    """
    from railtracks.vector_stores.chroma import ChromaVectorStore
    
    # Patch class_init to skip the actual Chroma client initialization
    with patch.object(ChromaVectorStore, "class_init"):
        # Set up the class-level _chroma to our mock
        ChromaVectorStore._chroma = chroma_mocks["client"]
        
        # Create a real store instance (but with patched class_init)
        store = ChromaVectorStore(
            collection_name="test_collection",
            embedding_function=mock_embedding_function,
            path="./test-data"
        )
        
        # Patch the instance's _collection to use our mock collection
        original_collection = store._collection
        store._collection = chroma_mocks["collection"]
        
        yield store
        
        # Restore original (cleanup)
        store._collection = original_collection



@pytest.fixture
def patch_all_chromadb_clients(*args):
    """Context manager that patches all chromadb client types simultaneously.
    
    This patches PersistentClient, HttpClient, and EphemeralClient in one call.
    The main client is the first patch (which can be asserted on), and the others
    are just patched to prevent accidental use.
    
    Yields:
        The first mock (typically the one being tested)
    
    Example:
        with patch_all_chromadb_clients("chromadb.PersistentClient") as mock_persistent:
            # Other clients are also patched
            reset_chroma_class()
            ChromaVectorStore.class_init(path="./test-data", host=None, port=None)
            mock_persistent.assert_called_once()
    """
    clients = ["chromadb.PersistentClient", "chromadb.HttpClient", "chromadb.EphemeralClient"]
    
    # Find which client is the main one (first arg)
    main_client = args[0] if args else "chromadb.PersistentClient"
    other_clients = [c for c in clients if c != main_client]
    
    with patch(main_client) as mock_main:
        with patch(other_clients[0]), patch(other_clients[1]):
            yield mock_main
