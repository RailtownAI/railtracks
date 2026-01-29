import pytest
from uuid import UUID
from railtracks.vector_stores.vector_store_base import (
    MetadataKeys,
    Metric,
    Chunk,
    SearchResult,
    FetchResult,
    SearchResponse,
    FetchResponse,
    OneOrMany,
    VectorStore,
)


class TestMetadataKeysEnum:
    """Tests for MetadataKeys enum."""

    def test_content_value(self):
        """Verify CONTENT enum value is correct."""
        assert MetadataKeys.CONTENT.value == "__content__"

    def test_document_value(self):
        """Verify DOCUMENT enum value is correct."""
        assert MetadataKeys.DOCUMENT.value == "__document__"

    def test_enum_members_by_name(self):
        """Verify enum members are accessible by name."""
        assert MetadataKeys["CONTENT"] == MetadataKeys.CONTENT
        assert MetadataKeys["DOCUMENT"] == MetadataKeys.DOCUMENT

    def test_enum_members_count(self):
        """Verify correct number of enum members."""
        assert len(list(MetadataKeys)) == 2


class TestMetricEnum:
    """Tests for Metric enum."""

    def test_cosine_value(self):
        """Verify cosine metric value."""
        assert Metric.cosine.value == "cosine"

    def test_l2_value(self):
        """Verify L2 metric value."""
        assert Metric.l2.value == "l2"

    def test_dot_value(self):
        """Verify dot metric value."""
        assert Metric.dot.value == "dot"

    def test_enum_members_count(self):
        """Verify correct number of enum members."""
        assert len(list(Metric)) == 3

    def test_enum_members_accessible_by_name(self):
        """Verify all metrics are accessible by name."""
        assert Metric["cosine"] == Metric.cosine
        assert Metric["l2"] == Metric.l2
        assert Metric["dot"] == Metric.dot

class TestSearchResultDataclass:
    """Tests for SearchResult dataclass."""

    def test_create_search_result_with_all_fields(self, simple_content, simple_document, short_vector, small_distance, simple_metadata):
        """Create SearchResult with all fields."""
        result = SearchResult(
            id="id1",
            distance=small_distance,
            content=simple_content,
            vector=short_vector,
            document=simple_document,
            metadata=simple_metadata
        )
        assert result.id == "id1"
        assert result.distance == small_distance
        assert result.content == simple_content
        assert result.vector == short_vector
        assert result.document == simple_document
        assert result.metadata == simple_metadata

    def test_create_search_result_with_required_fields(self, simple_content, short_vector, small_distance):
        """Create SearchResult with only required fields."""
        result = SearchResult(
            id="id1",
            distance=small_distance,
            content=simple_content,
            vector=short_vector
        )
        assert result.id == "id1"
        assert result.distance == small_distance
        assert result.content == simple_content
        assert result.vector == short_vector
        assert result.document is None
        assert result.metadata == {}

    def test_search_result_with_zero_distance(self, simple_content, short_vector, zero_distance):
        """Create SearchResult with zero distance."""
        result = SearchResult(
            id="id1",
            distance=zero_distance,
            content=simple_content,
            vector=short_vector
        )
        assert result.distance == zero_distance

    def test_search_result_with_large_vector(self, simple_content, large_distance, long_vector):
        """Create SearchResult with large vector."""
        result = SearchResult(
            id="id1",
            distance=large_distance,
            content=simple_content,
            vector=long_vector
        )
        assert len(result.vector) == 1000


class TestFetchResultDataclass:
    """Tests for FetchResult dataclass."""

    def test_create_fetch_result_with_all_fields(self, simple_content, simple_document, short_vector, simple_metadata):
        """Create FetchResult with all fields."""
        result = FetchResult(
            id="id1",
            content=simple_content,
            vector=short_vector,
            document=simple_document,
            metadata=simple_metadata
        )
        assert result.id == "id1"
        assert result.content == simple_content
        assert result.vector == short_vector
        assert result.document == simple_document
        assert result.metadata == simple_metadata

    def test_create_fetch_result_with_required_fields(self, simple_content, short_vector):
        """Create FetchResult with only required fields."""
        result = FetchResult(
            id="id1",
            content=simple_content,
            vector=short_vector
        )
        assert result.id == "id1"
        assert result.content == simple_content
        assert result.vector == short_vector
        assert result.document is None
        assert result.metadata == {}

    def test_fetch_result_with_custom_metadata(self, simple_content, simple_vector, complex_metadata):
        """Create FetchResult with custom metadata."""
        result = FetchResult(
            id="id1",
            content=simple_content,
            vector=simple_vector,
            metadata=complex_metadata
        )
        assert result.metadata == complex_metadata


class TestTypeAliases:
    """Tests for type aliases."""

    def test_search_response_is_list_of_search_result(self, simple_content, simple_vector, small_distance, large_distance):
        """Verify SearchResponse is a list of SearchResult."""
        result1 = SearchResult(id="1", distance=small_distance, content=simple_content, vector=simple_vector)
        result2 = SearchResult(id="2", distance=large_distance, content=simple_content, vector=simple_vector)
        
        response: SearchResponse = [result1, result2]
        
        assert isinstance(response, list)
        assert len(response) == 2
        assert all(isinstance(r, SearchResult) for r in response)

    def test_fetch_response_is_list_of_fetch_result(self, simple_content, simple_vector):
        """Verify FetchResponse is a list of FetchResult."""
        result1 = FetchResult(id="1", content=simple_content, vector=simple_vector)
        result2 = FetchResult(id="2", content=simple_content, vector=simple_vector)
        
        response: FetchResponse = [result1, result2]
        
        assert isinstance(response, list)
        assert len(response) == 2
        assert all(isinstance(r, FetchResult) for r in response)

    def test_one_or_many_with_single_value(self):
        """Test OneOrMany with single value."""
        value: OneOrMany[str] = "single"
        assert isinstance(value, str)

    def test_one_or_many_with_list(self):
        """Test OneOrMany with list value."""
        value: OneOrMany[str] = ["first", "second"]
        assert isinstance(value, list)
        assert len(value) == 2


class TestVectorStoreAbstractClass:
    """Tests for VectorStore abstract base class."""

    def test_cannot_instantiate_abstract_class(self):
        """Verify cannot instantiate abstract VectorStore directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            store = VectorStore(  # type: ignore[abstract]
                collection_name="test",
                embedding_function=lambda x: [[0.1]]
            )

    def test_all_abstract_methods_defined(self):
        """Verify all abstract methods are defined."""
        abstract_methods = VectorStore.__abstractmethods__
        
        expected_methods = {"upsert", "fetch", "search", "delete", "count"}
        assert abstract_methods == expected_methods

    def test_concrete_subclass_can_be_created(self):
        """Verify concrete subclass can be created by implementing all methods."""
        
        class ConcreteVectorStore(VectorStore):
            def upsert(self, content):
                return []
            
            def fetch(self, ids):
                return []
            
            def search(self, query, top_k=10, where=None, include=None):
                return []
            
            def delete(self, ids, where=None):
                pass
            
            def count(self):
                return 0
        
        # Should not raise
        store = ConcreteVectorStore(
            collection_name="test",
            embedding_function=lambda x: [[0.1]]
        )
        assert store._collection_name == "test"
