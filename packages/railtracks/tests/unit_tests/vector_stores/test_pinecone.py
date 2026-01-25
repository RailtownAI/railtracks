import pytest
from unittest.mock import MagicMock, patch, call
from railtracks.vector_stores.pinecone import PineconeVectorStore
from railtracks.vector_stores.vector_store_base import (
    Fields,
    SearchResult,
    MetadataKeys,
)


CONTENT = MetadataKeys.CONTENT.value
DOCUMENT = MetadataKeys.DOCUMENT.value


class TestPineconeVectorStoreClassInit:
    """Tests for PineconeVectorStore.class_init()."""

    def test_class_init_initializes_pinecone_client(self, reset_pinecone_class):
        """Test that Pinecone client is properly initialized."""
        with patch("railtracks.vector_stores.pinecone.Pinecone") as mock_pinecone_class, \
             patch("railtracks.vector_stores.pinecone.Vector"), \
             patch("railtracks.vector_stores.pinecone.ServerlessSpec"), \
             patch("railtracks.vector_stores.pinecone.IndexEmbed"):
            
            reset_pinecone_class()
            PineconeVectorStore.class_init(api_key="test-key")
            
            mock_pinecone_class.assert_called_once_with(api_key="test-key")

    def test_class_init_uses_env_api_key_by_default(self, reset_pinecone_class):
        """Test that PINECONE_API_KEY environment variable is used by default."""
        with patch.dict("os.environ", {"PINECONE_API_KEY": "env-key"}), \
             patch("railtracks.vector_stores.pinecone.Pinecone") as mock_pinecone_class, \
             patch("railtracks.vector_stores.pinecone.Vector"), \
             patch("railtracks.vector_stores.pinecone.ServerlessSpec"), \
             patch("railtracks.vector_stores.pinecone.IndexEmbed"):
            
            reset_pinecone_class()
            PineconeVectorStore.class_init()
            
            mock_pinecone_class.assert_called_once_with(api_key="env-key")

    def test_class_init_only_initializes_once(self, reset_pinecone_class):
        """Test that class_init only initializes the Pinecone client once."""
        with patch("railtracks.vector_stores.pinecone.Pinecone") as mock_pinecone_class, \
             patch("railtracks.vector_stores.pinecone.Vector"), \
             patch("railtracks.vector_stores.pinecone.ServerlessSpec"), \
             patch("railtracks.vector_stores.pinecone.IndexEmbed"):
            
            reset_pinecone_class()
            PineconeVectorStore.class_init(api_key="test-key")
            call_count_1 = mock_pinecone_class.call_count
            
            # Second call should NOT re-initialize
            PineconeVectorStore.class_init(api_key="test-key")
            call_count_2 = mock_pinecone_class.call_count
            
            assert call_count_1 == 1
            assert call_count_2 == 1

    def test_class_init_raises_import_error_without_pinecone(self, reset_pinecone_class):
        """Test that ImportError is raised if Pinecone is not installed."""
        reset_pinecone_class()
        
        with patch("builtins.__import__", side_effect=ImportError("No module named 'pinecone'")):
            with pytest.raises(ImportError, match="Pinecone package is not installed"):
                PineconeVectorStore.class_init(api_key="test-key")


class TestPineconeVectorStoreInit:
    """Tests for PineconeVectorStore.__init__()."""

    def test_init_manual_index_creation(self, mock_embedding_model, pinecone_mocks, reset_pinecone_class):
        """Test initialization with manual index creation parameters."""
        reset_pinecone_class()
        PineconeVectorStore._pc = pinecone_mocks["client"]
        PineconeVectorStore._Vector = pinecone_mocks["Vector"]
        PineconeVectorStore._ServerlessSpec = pinecone_mocks["ServerlessSpec"]
        PineconeVectorStore._IndexEmbed = pinecone_mocks["IndexEmbed"]
        
        store = PineconeVectorStore(
            collection_name="test_index",
            embedding_model=mock_embedding_model,
            api_key="test-key",
            vector_type="dense",
            dimension=384,
            metric="cosine",
            cloud="aws",
            region="us-west-2",
            deletion_protection="disabled"
        )
        
        assert store._collection_name == "test_index"
        assert store._embedding_model == mock_embedding_model
        pinecone_mocks["client"].create_index.assert_called_once()

    def test_init_integrated_model_index_creation(self, mock_embedding_model, pinecone_mocks, reset_pinecone_class):
        """Test initialization with integrated embedding model."""
        reset_pinecone_class()
        PineconeVectorStore._pc = pinecone_mocks["client"]
        PineconeVectorStore._Vector = pinecone_mocks["Vector"]
        PineconeVectorStore._ServerlessSpec = pinecone_mocks["ServerlessSpec"]
        PineconeVectorStore._IndexEmbed = pinecone_mocks["IndexEmbed"]
        
        store = PineconeVectorStore(
            collection_name="test_index",
            embedding_model=mock_embedding_model,
            api_key="test-key",
            cloud="aws",
            region="us-west-2",
            field_map={"text": "content"},
            deletion_protection="disabled"
        )
        
        assert store._collection_name == "test_index"
        pinecone_mocks["client"].create_index_for_model.assert_called_once()

    def test_init_connect_to_existing_index(self, mock_embedding_model, pinecone_mocks, reset_pinecone_class):
        """Test initialization by connecting to an existing index."""
        reset_pinecone_class()
        PineconeVectorStore._pc = pinecone_mocks["client"]
        PineconeVectorStore._Vector = pinecone_mocks["Vector"]
        PineconeVectorStore._ServerlessSpec = pinecone_mocks["ServerlessSpec"]
        PineconeVectorStore._IndexEmbed = pinecone_mocks["IndexEmbed"]
        pinecone_mocks["client"].has_index.return_value = True
        
        store = PineconeVectorStore(
            collection_name="existing_index",
            embedding_model=mock_embedding_model,
            api_key="test-key"
        )
        
        assert store._collection_name == "existing_index"
        pinecone_mocks["client"].has_index.assert_called_once_with("existing_index")
        pinecone_mocks["client"].describe_index.assert_called_once()

    def test_init_missing_index_raises_error(self, mock_embedding_model, pinecone_mocks, reset_pinecone_class):
        """Test ValueError when connecting to non-existent index."""
        reset_pinecone_class()
        PineconeVectorStore._pc = pinecone_mocks["client"]
        PineconeVectorStore._Vector = pinecone_mocks["Vector"]
        PineconeVectorStore._ServerlessSpec = pinecone_mocks["ServerlessSpec"]
        PineconeVectorStore._IndexEmbed = pinecone_mocks["IndexEmbed"]
        pinecone_mocks["client"].has_index.return_value = False
        
        with pytest.raises(ValueError, match="does not exist"):
            PineconeVectorStore(
                collection_name="missing_index",
                embedding_model=mock_embedding_model,
                api_key="test-key"
            )

    def test_init_invalid_params_raises_error(self, mock_embedding_model, pinecone_mocks, reset_pinecone_class):
        """Test ValueError for invalid parameter combinations."""
        reset_pinecone_class()
        PineconeVectorStore._pc = pinecone_mocks["client"]
        PineconeVectorStore._Vector = pinecone_mocks["Vector"]
        PineconeVectorStore._ServerlessSpec = pinecone_mocks["ServerlessSpec"]
        PineconeVectorStore._IndexEmbed = pinecone_mocks["IndexEmbed"]
        
        with pytest.raises(ValueError, match="Incorrect pass of parameters"):
            PineconeVectorStore(
                collection_name="test_index",
                embedding_model=mock_embedding_model,
                api_key="test-key",
                vector_type="dense",
                dimension=384,
                # Missing metric, cloud, region
            )


class TestPineconeVectorStoreUpsert:
    """Tests for PineconeVectorStore.upsert()."""

    @pytest.mark.parametrize(
        "content,expected_return_type",
        [
            ("Test content", str),
            (["Content 1", "Content 2", "Content 3"], list),
        ],
    )
    def test_upsert_strings_returns_ids(self, pinecone_store, pinecone_mocks, content, expected_return_type):
        """Test upserting strings returns correct ID type."""
        result = pinecone_store.upsert(content)
        
        assert isinstance(result, expected_return_type)
        pinecone_mocks["collection"].upsert.assert_called_once()

    def test_upsert_single_chunk_returns_string_id(self, pinecone_store, sample_chunk, pinecone_mocks):
        """Test upserting a single Chunk returns single ID."""
        result = pinecone_store.upsert(sample_chunk)
        
        assert isinstance(result, str)
        pinecone_mocks["collection"].upsert.assert_called_once()

    def test_upsert_list_of_chunks_returns_list_of_ids(self, pinecone_store, sample_chunks, pinecone_mocks):
        """Test upserting a list of Chunks returns list of IDs."""
        result = pinecone_store.upsert(sample_chunks)
        
        assert isinstance(result, list)
        assert len(result) == 3
        pinecone_mocks["collection"].upsert.assert_called_once()

    def test_upsert_metadata_includes_content_key(self, pinecone_store, sample_chunk, pinecone_mocks):
        """Test metadata includes CONTENT key."""
        pinecone_store.upsert(sample_chunk)
        
        call_args = pinecone_mocks["collection"].upsert.call_args
        vectors = call_args.kwargs["vectors"]
        assert any(CONTENT in v.metadata for v in vectors)

    def test_upsert_string_metadata_has_content_only(self, pinecone_store, pinecone_mocks):
        """Test string upsert creates metadata with content."""
        test_string = "Test content"
        pinecone_store.upsert(test_string)
        
        call_args = pinecone_mocks["collection"].upsert.call_args
        vectors = call_args.kwargs["vectors"]
        assert vectors[0].metadata[CONTENT] == test_string

    def test_upsert_document_stored_when_present(self, pinecone_store, sample_chunk, pinecone_mocks):
        """Test document field is stored when present."""
        pinecone_store.upsert(sample_chunk)
        
        call_args = pinecone_mocks["collection"].upsert.call_args
        vectors = call_args.kwargs["vectors"]
        assert DOCUMENT in vectors[0].metadata

    def test_upsert_generates_embeddings(self, pinecone_store, pinecone_mocks):
        """Test embeddings are generated via embedding model."""
        pinecone_store.upsert(["Content 1", "Content 2"])
        
        call_args = pinecone_mocks["collection"].upsert.call_args
        vectors = call_args.kwargs["vectors"]
        assert len(vectors) == 2


class TestPineconeVectorStoreFetch:
    """Tests for PineconeVectorStore.fetch()."""

    def test_fetch_with_single_id(self, pinecone_store, pinecone_mocks):
        """Test fetching with single ID."""
        pinecone_mocks["collection"].fetch.return_value = {
            "vectors": {
                "id1": {
                    "id": "id1",
                    "values": [0.1, 0.2, 0.3, 0.4, 0.5],
                    "metadata": {CONTENT: "Test content", "key": "value"}
                }
            }
        }
        
        result = pinecone_store.fetch(ids="id1")
        
        assert isinstance(result, list)
        assert len(result) == 1

    def test_fetch_with_list_of_ids(self, pinecone_store, pinecone_mocks):
        """Test fetching with list of IDs."""
        pinecone_mocks["collection"].fetch.return_value = {
            "vectors": {
                "id1": {
                    "id": "id1",
                    "values": [0.1, 0.2, 0.3, 0.4, 0.5],
                    "metadata": {CONTENT: "Content 1"}
                },
                "id2": {
                    "id": "id2",
                    "values": [0.2, 0.3, 0.4, 0.5, 0.6],
                    "metadata": {CONTENT: "Content 2"}
                }
            }
        }
        
        result = pinecone_store.fetch(ids=["id1", "id2"])
        
        assert isinstance(result, list)
        assert len(result) == 2

    def test_fetch_extracts_content_from_metadata(self, pinecone_store, pinecone_mocks):
        """Test CONTENT is extracted from metadata."""
        test_content = "Extracted content"
        pinecone_mocks["collection"].fetch.return_value = {
            "vectors": {
                "id1": {
                    "id": "id1",
                    "values": [0.1, 0.2, 0.3, 0.4, 0.5],
                    "metadata": {CONTENT: test_content}
                }
            }
        }
        
        result = pinecone_store.fetch(ids="id1")
        
        assert result[0].content == test_content

    def test_fetch_with_where_filter(self, pinecone_store, pinecone_mocks):
        """Test fetch with metadata filter."""
        pinecone_mocks["collection"].fetch_by_metadata.return_value = {
            "vectors": {
                "id1": {
                    "id": "id1",
                    "values": [0.1, 0.2, 0.3, 0.4, 0.5],
                    "metadata": {CONTENT: "Filtered content"}
                }
            }
        }
        
        result = pinecone_store.fetch(where={"key": "value"})  # type: ignore[arg-type]
        
        pinecone_mocks["collection"].fetch_by_metadata.assert_called_once()

    def test_fetch_missing_content_raises_error(self, pinecone_store, pinecone_mocks):
        """Test ValueError when CONTENT key missing."""
        pinecone_mocks["collection"].fetch.return_value = {
            "vectors": {
                "id1": {
                    "id": "id1",
                    "values": [0.1, 0.2, 0.3, 0.4, 0.5],
                    "metadata": {"other_key": "value"}
                }
            }
        }
        
        with pytest.raises((ValueError, KeyError)):
            pinecone_store.fetch(ids="id1")


class TestPineconeVectorStoreSearch:
    """Tests for PineconeVectorStore.search()."""

    def test_search_single_string_query_dense(self, pinecone_store_dense, pinecone_mocks):
        """Test searching with single string query (dense vectors)."""
        pinecone_mocks["collection"].query.return_value = {
            "matches": [
                {
                    "id": "id1",
                    "score": 0.9,
                    "values": [0.1, 0.2, 0.3, 0.4, 0.5],
                    "metadata": {CONTENT: "Content 1"}
                }
            ]
        }
        
        result = pinecone_store_dense.search("Query text")
        
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(item, SearchResult) for item in result)

    def test_search_list_of_string_queries_dense(self, pinecone_store_dense, pinecone_mocks):
        """Test searching with list of queries (dense vectors)."""
        pinecone_mocks["collection"].query.return_value = {
            "matches": [
                {
                    "id": "id1",
                    "score": 0.9,
                    "values": [0.1, 0.2, 0.3, 0.4, 0.5],
                    "metadata": {CONTENT: "Content 1"}
                }
            ]
        }
        
        result = pinecone_store_dense.search(["Query 1", "Query 2"])
        
        assert isinstance(result, list)
        assert len(result) == 2

    def test_search_single_string_query_sparse(self, pinecone_store_sparse, pinecone_mocks):
        """Test searching with single string query (sparse vectors)."""
        pinecone_mocks["collection"].search.return_value = {
            "result": {
                "hits": [
                    {
                        "_id": "id1",
                        "_score": 0.9,
                        "fields": {CONTENT: "Content 1"}
                    }
                ]
            }
        }
        
        result = pinecone_store_sparse.search("Query text")
        
        assert isinstance(result, list)

    def test_search_top_k_parameter(self, pinecone_store_dense, pinecone_mocks):
        """Test top_k parameter controls result count."""
        pinecone_mocks["collection"].query.return_value = {
            "matches": [
                {
                    "id": f"id{i}",
                    "score": 0.9 - (i * 0.1),
                    "values": [0.1 * (i + 1)] * 5,
                    "metadata": {CONTENT: f"Content {i}"}
                }
                for i in range(1, 4)
            ]
        }
        
        pinecone_store_dense.search("Query", top_k=3)
        
        call_args = pinecone_mocks["collection"].query.call_args
        assert call_args.kwargs["top_k"] == 3

    def test_search_with_where_filter(self, pinecone_store_dense, pinecone_mocks):
        """Test search with metadata filter."""
        pinecone_mocks["collection"].query.return_value = {
            "matches": [
                {
                    "id": "id1",
                    "score": 0.9,
                    "values": [0.1, 0.2, 0.3, 0.4, 0.5],
                    "metadata": {CONTENT: "Filtered content"}
                }
            ]
        }
        
        pinecone_store_dense.search("Query", where={"key": "value"})  # type: ignore[arg-type]
        
        call_args = pinecone_mocks["collection"].query.call_args
        assert call_args.kwargs["filter"] is not None


class TestPineconeVectorStoreDelete:
    """Tests for PineconeVectorStore.delete()."""

    @pytest.mark.parametrize(
        "delete_input",
        [
            "id1",
            ["id1", "id2", "id3"],
        ],
    )
    def test_delete_by_id(self, pinecone_store, pinecone_mocks, delete_input):
        """Test deleting by single ID or list of IDs."""
        pinecone_store.delete(ids=delete_input)
        
        pinecone_mocks["collection"].delete.assert_called_once()

    def test_delete_with_where_filter(self, pinecone_store, pinecone_mocks):
        """Test delete with metadata filter."""
        pinecone_store.delete(where={"status": "archived"})  # type: ignore[arg-type]
        
        call_args = pinecone_mocks["collection"].delete.call_args
        assert call_args.kwargs["filter"] is not None


class TestPineconeVectorStoreCount:
    """Tests for PineconeVectorStore.count()."""

    @pytest.mark.parametrize(
        "mock_count,expected_result",
        [
            (42, 42),
            (0, 0),
            (1, 1),
            (999, 999),
        ],
    )
    def test_count_returns_collection_size(self, pinecone_store, pinecone_mocks, mock_count, expected_result):
        """Test count returns correct collection size."""
        pinecone_mocks["collection"].describe_index_stats.return_value = {
            "total_vector_count": mock_count
        }
        
        result = pinecone_store.count()
        
        assert isinstance(result, int)
        assert result == expected_result


class TestPineconeVectorStoreIntegration:
    """Integration tests for PineconeVectorStore."""

    def test_workflow_upsert_search_fetch(self, pinecone_store, pinecone_mocks):
        """Test full workflow: upsert → search → fetch."""
        # Upsert
        pinecone_store.upsert(["Content 1", "Content 2"])
        assert pinecone_mocks["collection"].upsert.called
        
        # Search
        pinecone_mocks["collection"].query.return_value = {
            "matches": [
                {
                    "id": "id1",
                    "score": 0.9,
                    "values": [0.1, 0.2, 0.3, 0.4, 0.5],
                    "metadata": {CONTENT: "Content 1"}
                }
            ]
        }
        search_result = pinecone_store.search("Query")
        assert isinstance(search_result, list)
        
        # Fetch
        pinecone_mocks["collection"].fetch.return_value = {
            "vectors": {
                "id1": {
                    "id": "id1",
                    "values": [0.1, 0.2, 0.3, 0.4, 0.5],
                    "metadata": {CONTENT: "Content 1"}
                }
            }
        }
        fetch_result = pinecone_store.fetch(ids="id1")
        assert isinstance(fetch_result, list)

