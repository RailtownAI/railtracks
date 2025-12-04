import pytest
from unittest.mock import MagicMock, patch, call
from uuid import uuid4
from railtracks.vector_stores.chroma import ChromaVectorStore
from railtracks.vector_stores.vector_store_base import (
    MetadataKeys,
    SearchResult,
)


CONTENT = MetadataKeys.CONTENT.value
DOCUMENT = MetadataKeys.DOCUMENT.value


class TestChromaVectorStoreClassInit:
    """Tests for ChromaVectorStore.class_init()."""

    @pytest.mark.parametrize(
        "path,host,port,expected_mock,expected_args",
        [
            ("./test-data", None, None, "mock_persistent", {"path": "./test-data"}),
            (None, "localhost", 8000, "mock_http", {"host": "localhost", "port": 8000}),
            (None, None, None, "mock_ephemeral", {}),
        ],
    )
    def test_class_init_creates_correct_client(self, path, host, port, expected_mock, expected_args, reset_chroma_class):
        """Test that correct client is instantiated based on parameters."""
        with patch("chromadb.PersistentClient") as mock_persistent, \
             patch("chromadb.HttpClient") as mock_http, \
             patch("chromadb.EphemeralClient") as mock_ephemeral:
            
            mocks = {
                "mock_persistent": mock_persistent,
                "mock_http": mock_http,
                "mock_ephemeral": mock_ephemeral,
            }

            reset_chroma_class()
            ChromaVectorStore.class_init(path=path, host=host, port=port)
            
            for name, mock in mocks.items():
                if name == expected_mock:
                    mock.assert_called_once_with(**expected_args)
                else:
                    mock.assert_not_called()

    @pytest.mark.parametrize(
        "path,host,port",
        [
            ("./path", "localhost", 8000),  # path + host + port
            ("./path", "localhost", None),  # path + host
            ("./path", None, 8000),  # path + port
            (None, "localhost", None),  # host without port
            (None, None, 8000),  # port without host
        ],
    )
    def test_class_init_invalid_params_raises_value_error(self, path, host, port, reset_chroma_class, patch_all_chromadb_clients):
        """Test invalid parameter combinations raise ValueError."""
        with patch_all_chromadb_clients():
            reset_chroma_class()
            
            with pytest.raises(ValueError, match="Invalid combination"):
                ChromaVectorStore.class_init(path=path, host=host, port=port)

    def test_class_init_only_initializes_class_once(self, reset_chroma_class):
        """Test multiple calls don't re-initialize."""
        with patch("chromadb.EphemeralClient") as mock_ephemeral:
            reset_chroma_class()
            ChromaVectorStore.class_init(path=None, host=None, port=None)
            call_count_1 = mock_ephemeral.call_count
            
            # Second call should NOT instantiate a new client
            ChromaVectorStore.class_init(path=None, host=None, port=None)
            call_count_2 = mock_ephemeral.call_count
            
            assert call_count_1 == 1
            assert call_count_2 == 1  # Still 1, not incremented


class TestChromaVectorStoreInit:
    """Tests for ChromaVectorStore.__init__()."""

    @pytest.mark.parametrize(
        "collection_name,path,host,port",
        [
            ("test_collection", "./test-data", None, None),
            ("remote_collection", None, "localhost", 8000),
            ("temp_collection", None, None, None),
        ],
    )
    def test_init_with_different_configs(self, mock_embedding_function, collection_name, path, host, port, patch_all_chromadb_clients):
        """Test initialization with different configuration parameters."""
        with patch.object(ChromaVectorStore, "class_init") as mock_class_init:
            with patch_all_chromadb_clients():
                mock_client = MagicMock()
                mock_collection = MagicMock()
                mock_client.get_or_create_collection.return_value = mock_collection
                ChromaVectorStore._chroma = mock_client
                
                init_kwargs = {
                    "collection_name": collection_name,
                    "embedding_function": mock_embedding_function,
                }
                if path is not None:
                    init_kwargs["path"] = path
                if host is not None:
                    init_kwargs["host"] = host
                if port is not None:
                    init_kwargs["port"] = port
                
                store = ChromaVectorStore(**init_kwargs)
                
                assert store._collection_name == collection_name
                assert store._embedding_function == mock_embedding_function
                assert store._collection == mock_collection
                assert ChromaVectorStore._chroma == mock_client
                mock_class_init.assert_called_once()


class TestChromaVectorStoreUpsert:
    """Tests for ChromaVectorStore.upsert()."""

    @pytest.mark.parametrize(
        "content,expected_return_type",
        [
            ("Test content", str),
            (["Content 1", "Content 2", "Content 3"], list),
        ],
    )
    def test_upsert_strings_returns_ids_matching_chroma(self, chroma_store, chroma_mocks, content, expected_return_type):
        """Test upserting strings returns correct ID type and matches what was sent to Chroma."""
        result = chroma_store.upsert(content)
        
        assert isinstance(result, expected_return_type)
        chroma_mocks["collection"].upsert.assert_called_once()
        call_args = chroma_mocks["collection"].upsert.call_args
        
        # Returned IDs should match what was passed to Chroma
        assert result == (call_args.kwargs["ids"][0] if expected_return_type == str else call_args.kwargs["ids"])

    def test_upsert_single_chunk_returns_string_id(self, chroma_store, sample_chunk, chroma_mocks):
        """Test upserting a single Chunk returns single ID."""
        result = chroma_store.upsert(sample_chunk)
        
        assert isinstance(result, str)
        chroma_mocks["collection"].upsert.assert_called_once()
        call_args = chroma_mocks["collection"].upsert.call_args
        # Chunk uses its own ID, so verify it matches
        assert result == sample_chunk.id

    def test_upsert_list_of_chunks_returns_list_of_ids(self, chroma_store, sample_chunks, chroma_mocks):
        """Test upserting a list of Chunks returns list of IDs."""
        result = chroma_store.upsert(sample_chunks)
        
        assert isinstance(result, list)
        chroma_mocks["collection"].upsert.assert_called_once()
        call_args = chroma_mocks["collection"].upsert.call_args
        # Chunks use their own IDs
        expected_ids = [chunk.id for chunk in sample_chunks]
        assert result == expected_ids

    def test_upsert_metadata_includes_content_key(self, chroma_store, sample_chunk, chroma_mocks):
        """Test metadata includes CONTENT key."""
        chroma_store.upsert(sample_chunk)
        
        call_args = chroma_mocks["collection"].upsert.call_args
        metadatas = call_args.kwargs["metadatas"]
        assert CONTENT in metadatas[0]
        assert metadatas[0][CONTENT] == sample_chunk.content

    def test_upsert_string_metadata_has_content_only(self, chroma_store, chroma_mocks):
        """Test string upsert creates metadata with content only."""
        test_string = "Test content"
        chroma_store.upsert(test_string)
        
        call_args = chroma_mocks["collection"].upsert.call_args
        metadatas = call_args.kwargs["metadatas"]
        assert metadatas[0][CONTENT] == test_string

    def test_upsert_document_stored_when_present(self, chroma_store, sample_chunk, chroma_mocks):
        """Test document field is stored when present."""
        chroma_store.upsert(sample_chunk)
        
        call_args = chroma_mocks["collection"].upsert.call_args
        documents = call_args.kwargs["documents"]
        assert documents[0] == sample_chunk.document

    def test_upsert_document_none_when_string(self, chroma_store, chroma_mocks):
        """Test document is None when upserting string."""
        chroma_store.upsert("Test string")
        
        call_args = chroma_mocks["collection"].upsert.call_args
        documents = call_args.kwargs["documents"]
        assert documents[0] is None
        

    def test_upsert_generates_embeddings(self, chroma_store, chroma_mocks):
        """Test embeddings are generated via embedding function."""
        chroma_store.upsert(["Content 1", "Content 2"])
        
        call_args = chroma_mocks["collection"].upsert.call_args
        embeddings = call_args.kwargs["embeddings"]
        assert len(embeddings) == 2
        assert all(len(e) == 5 for e in embeddings)


class TestChromaVectorStoreFetch:
    """Tests for ChromaVectorStore.fetch()."""

    def test_fetch_with_single_id(self, chroma_store, chroma_mocks):
        """Test fetching with single ID."""
        # Setup mock response
        chroma_mocks["collection"].get.return_value = {
            "ids": ["id1"],
            "embeddings": [[0.1, 0.2, 0.3, 0.4, 0.5]],
            "documents": ["doc.txt"],
            "metadatas": [{CONTENT: "Test content", "key": "value"}]
        }
        
        result = chroma_store.fetch("id1")
        
        assert isinstance(result, list)
        assert len(result) == 1

    def test_fetch_with_list_of_ids(self, chroma_store, chroma_mocks):
        """Test fetching with list of IDs."""
        chroma_mocks["collection"].get.return_value = {
            "ids": ["id1", "id2"],
            "embeddings": [[0.1, 0.2, 0.3, 0.4, 0.5], [0.2, 0.3, 0.4, 0.5, 0.6]],
            "documents": ["doc1.txt", "doc2.txt"],
            "metadatas": [
                {CONTENT: "Content 1", "key": "value1"},
                {CONTENT: "Content 2", "key": "value2"}
            ]
        }
        
        result = chroma_store.fetch(["id1", "id2"])
        
        assert isinstance(result, list)
        assert len(result) == 2

    def test_fetch_extracts_content_from_metadata(self, chroma_store, chroma_mocks):
        """Test CONTENT is extracted from metadata."""
        test_content = "Extracted content"
        chroma_mocks["collection"].get.return_value = {
            "ids": ["id1"],
            "embeddings": [[0.1, 0.2, 0.3, 0.4, 0.5]],
            "documents": ["doc.txt"],
            "metadatas": [{CONTENT: test_content}]
        }
        
        result = chroma_store.fetch("id1")
        
        assert result[0].content == test_content

    def test_fetch_removes_content_from_returned_metadata(self, chroma_store, chroma_mocks):
        """Test CONTENT key is removed from returned metadata."""
        chroma_mocks["collection"].get.return_value = {
            "ids": ["id1"],
            "embeddings": [[0.1, 0.2, 0.3, 0.4, 0.5]],
            "documents": ["doc.txt"],
            "metadatas": [{CONTENT: "Content", "custom_key": "custom_value"}]
        }
        
        result = chroma_store.fetch("id1")
        
        assert CONTENT not in result[0].metadata
        assert result[0].metadata["custom_key"] == "custom_value"

    def test_fetch_extracts_document(self, chroma_store, chroma_mocks):
        """Test document is extracted when present."""
        test_doc = "source_document.txt"
        chroma_mocks["collection"].get.return_value = {
            "ids": ["id1"],
            "embeddings": [[0.1, 0.2, 0.3, 0.4, 0.5]],
            "documents": [test_doc],
            "metadatas": [{CONTENT: "Content"}]
        }
        
        result = chroma_store.fetch("id1")
        
        assert result[0].document == test_doc

    def test_fetch_missing_embeddings_raises_error(self, chroma_store, chroma_mocks):
        """Test ValueError when embeddings missing in response."""
        chroma_mocks["collection"].get.return_value = {
            "ids": ["id1"],
            "documents": ["doc.txt"],
            "metadatas": [{CONTENT: "Content"}]
        }
        
        with pytest.raises(ValueError, match="Embeddings"):
            chroma_store.fetch("id1")

    def test_fetch_missing_content_raises_error(self, chroma_store, chroma_mocks):
        """Test ValueError when CONTENT key missing."""
        chroma_mocks["collection"].get.return_value = {
            "ids": ["id1"],
            "embeddings": [[0.1, 0.2, 0.3, 0.4, 0.5]],
            "documents": ["doc.txt"],
            "metadatas": [{"other_key": "value"}]
        }
        
        with pytest.raises(ValueError, match="Content was not initialized"):
            chroma_store.fetch("id1")


class TestChromaVectorStoreSearch:
    """Tests for ChromaVectorStore.search()."""

    def test_search_single_string_query(self, chroma_store, chroma_mocks):
        """Test searching with single string query returns SearchResponse."""
        chroma_mocks["collection"].query.return_value = {
            "ids": [["id1", "id2"]],
            "distances": [[0.1, 0.2]],
            "embeddings": [[[0.1, 0.2, 0.3, 0.4, 0.5], [0.2, 0.3, 0.4, 0.5, 0.6]]],
            "documents": [["doc1.txt", "doc2.txt"]],
            "metadatas": [[{CONTENT: "Content 1"}, {CONTENT: "Content 2"}]]
        }
        
        result = chroma_store.search("Query text")
        
        # Should return single SearchResponse (not list)
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(item, SearchResult) for item in result)

    def test_search_list_of_string_queries(self, chroma_store, chroma_mocks):
        """Test searching with list of string queries returns list[SearchResponse]."""
        chroma_mocks["collection"].query.return_value = {
            "ids": [["id1", "id2"], ["id3", "id4"]],
            "distances": [[0.1, 0.2], [0.3, 0.4]],
            "embeddings": [
                [[0.1, 0.2, 0.3, 0.4, 0.5], [0.2, 0.3, 0.4, 0.5, 0.6]],
                [[0.3, 0.4, 0.5, 0.6, 0.7], [0.4, 0.5, 0.6, 0.7, 0.8]]
            ],
            "documents": [["doc1.txt", "doc2.txt"], ["doc3.txt", "doc4.txt"]],
            "metadatas": [
                [{CONTENT: "Content 1"}, {CONTENT: "Content 2"}],
                [{CONTENT: "Content 3"}, {CONTENT: "Content 4"}]
            ]
        }
        
        result = chroma_store.search(["Query 1", "Query 2"])
        
        assert isinstance(result, list)
        assert len(result) == 2

    def test_search_with_single_chunk_query(self, chroma_store, sample_chunk, chroma_mocks):
        """Test searching with single Chunk query."""
        chroma_mocks["collection"].query.return_value = {
            "ids": [["id1"]],
            "distances": [[0.1]],
            "embeddings": [[[0.1, 0.2, 0.3, 0.4, 0.5]]],
            "documents": [["doc.txt"]],
            "metadatas": [[{CONTENT: "Content"}]]
        }
        
        result = chroma_store.search(sample_chunk)
        
        assert isinstance(result, list)

    def test_search_top_k_parameter(self, mock_embedding_function, chroma_mocks):
        """Test top_k parameter controls result count."""
        with patch.object(ChromaVectorStore, "class_init"):
            ChromaVectorStore._chroma = chroma_mocks["client"]
            
            store = ChromaVectorStore(
                collection_name="test",
                embedding_function=mock_embedding_function
            )
            
            chroma_mocks["collection"].query.return_value = {
                "ids": [["id1", "id2", "id3"]],
                "distances": [[0.1, 0.2, 0.3]],
                "embeddings": [[[0.1] * 5, [0.2] * 5, [0.3] * 5]],
                "documents": [["doc1.txt", "doc2.txt", "doc3.txt"]],
                "metadatas": [[{CONTENT: f"Content {i}"} for i in range(1, 4)]]
            }
            
            store.search("Query", top_k=3)
            
            call_args = chroma_mocks["collection"].query.call_args
            assert call_args.kwargs["n_results"] == 3

    def test_search_invalid_query_type_raises_error(self, mock_embedding_function, chroma_mocks):
        """Test ValueError for invalid query types."""
        with patch.object(ChromaVectorStore, "class_init"):
            ChromaVectorStore._chroma = chroma_mocks["client"]
            
            store = ChromaVectorStore(
                collection_name="test",
                embedding_function=mock_embedding_function
            )
            
            with pytest.raises(ValueError, match="Query must be"):
                store.search(123)  # type: ignore[arg-type]

    def test_search_where_filter_applied(self, mock_embedding_function, chroma_mocks):
        """Test where filter is applied."""
        with patch.object(ChromaVectorStore, "class_init"):
            ChromaVectorStore._chroma = chroma_mocks["client"]
            
            store = ChromaVectorStore(
                collection_name="test",
                embedding_function=mock_embedding_function
            )
            
            chroma_mocks["collection"].query.return_value = {
                "ids": [[]],
                "distances": [[]],
                "embeddings": [[]],
                "documents": [[]],
                "metadatas": [[]]
            }
            
            where_filter = {"key": "value"}
            store.search("Query", where=where_filter)  # type: ignore[arg-type]
            
            call_args = chroma_mocks["collection"].query.call_args
            assert call_args.kwargs["where"] == where_filter


class TestChromaVectorStoreDelete:
    """Tests for ChromaVectorStore.delete()."""

    @pytest.mark.parametrize(
        "delete_input",
        [
            "id1",
            ["id1", "id2", "id3"],
        ],
    )
    def test_delete_by_id(self, chroma_store, chroma_mocks, delete_input):
        """Test deleting by single ID or list of IDs."""
        chroma_store.delete(delete_input)
        
        chroma_mocks["collection"].delete.assert_called_once()

    def test_delete_with_where_filter(self, chroma_store, chroma_mocks):
        """Test delete with where filter."""
        where_filter = {"status": "archived"}
        chroma_store.delete(["id1"], where=where_filter)  # type: ignore[arg-type]
        
        call_args = chroma_mocks["collection"].delete.call_args
        assert call_args.kwargs["where"] == where_filter


class TestChromaVectorStoreCount:
    """Tests for ChromaVectorStore.count()."""

    @pytest.mark.parametrize(
        "mock_count,expected_result",
        [
            (42, 42),
            (0, 0),
            (1, 1),
            (999, 999),
        ],
    )
    def test_count_returns_collection_size(self, chroma_store, chroma_mocks, mock_count, expected_result):
        """Test count returns correct collection size."""
        chroma_mocks["collection"].count.return_value = mock_count
        
        result = chroma_store.count()
        
        assert isinstance(result, int)
        assert result == expected_result


class TestChromaVectorStoreIntegration:
    """Integration tests for ChromaVectorStore."""

    def test_workflow_upsert_search_fetch(self, chroma_store, chroma_mocks):
        """Test full workflow: upsert → search → fetch."""
        # Upsert
        chroma_store.upsert(["Content 1", "Content 2"])
        assert chroma_mocks["collection"].upsert.called
        
        # Search
        chroma_mocks["collection"].query.return_value = {
            "ids": [["id1"]],
            "distances": [[0.1]],
            "embeddings": [[[0.1, 0.2, 0.3, 0.4, 0.5]]],
            "documents": [["doc.txt"]],
            "metadatas": [[{CONTENT: "Content 1"}]]
        }
        search_result = chroma_store.search("Query")
        assert isinstance(search_result, list)
        
        # Fetch
        chroma_mocks["collection"].get.return_value = {
            "ids": ["id1"],
            "embeddings": [[0.1, 0.2, 0.3, 0.4, 0.5]],
            "documents": ["doc.txt"],
            "metadatas": [{CONTENT: "Content 1"}]
        }
        fetch_result = chroma_store.fetch("id1")
        assert isinstance(fetch_result, list)
