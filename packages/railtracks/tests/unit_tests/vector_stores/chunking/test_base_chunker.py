from uuid import UUID
from unittest.mock import patch
import pytest

from railtracks.vector_stores.chunking.base_chunker import BaseChunker
from railtracks.vector_stores import Chunk, MediaParser

class TestChunkDataclass:
    """Tests for Chunk dataclass."""

    def test_create_chunk_with_all_fields(self, custom_id, simple_content, simple_document, simple_metadata):
        """Create Chunk with all fields populated."""
        chunk = Chunk(
            content=simple_content,
            id=custom_id,
            document=simple_document,
            metadata=simple_metadata
        )
        assert chunk.content == simple_content
        assert chunk.id == custom_id
        assert chunk.document == simple_document
        assert chunk.metadata == simple_metadata

    def test_create_chunk_with_required_field_only(self, simple_content):
        """Create Chunk with only required content field."""
        chunk = Chunk(content=simple_content)
        assert chunk.content == simple_content
        assert chunk.id is not None
        assert chunk.document is None
        assert chunk.metadata == {}

    def test_id_auto_generated_when_not_provided(self, simple_content):
        """Verify id is auto-generated when not provided."""
        chunk1 = Chunk(content=simple_content)
        chunk2 = Chunk(content=simple_content)
        
        assert chunk1.id is not None
        assert chunk2.id is not None
        assert chunk1.id != chunk2.id
        # Verify it's a valid UUID string
        try:
            UUID(chunk1.id)
        except ValueError:
            pytest.fail(f"Generated id {chunk1.id} is not a valid UUID")

    def test_id_not_regenerated_when_provided(self, simple_content, custom_id):
        """Verify provided id is not changed."""
        chunk = Chunk(content=simple_content, id=custom_id)
        assert chunk.id == custom_id

    def test_post_init_initializes_empty_metadata_by_default(self, simple_content):
        """Verify __post_init__ initializes empty metadata by default."""
        chunk = Chunk(content=simple_content)
        assert chunk.metadata == {}
        assert isinstance(chunk.metadata, dict)

    def test_chunk_with_custom_metadata(self, simple_content, complex_metadata):
        """Create Chunk with custom metadata."""
        chunk = Chunk(content=simple_content, metadata=complex_metadata)
        assert chunk.metadata == complex_metadata
        assert chunk.document is None
        assert chunk.id is not None


class ConcreteChunker(BaseChunker):
    """Concrete implementation of BaseChunker for testing."""

    def split_text(self, text: str) -> list[str]:
        """Simple split by newlines for testing."""
        return text.split("\n")


class TestBaseChunker:
    """Tests for the BaseChunker abstract base class."""

    def test_initialization_with_defaults(self):
        """Test chunker initialization with default parameters."""
        chunker = ConcreteChunker()

        assert chunker.chunk_size == 400
        assert chunker.overlap == 200

    def test_initialization_with_custom_values(self):
        """Test chunker initialization with custom parameters."""
        chunker = ConcreteChunker(chunk_size=1000, overlap=100)

        assert chunker.chunk_size == 1000
        assert chunker.overlap == 100

    def test_initialization_fails_when_overlap_equals_chunk_size(self):
        """Test that initialization fails when overlap equals chunk_size."""
        with pytest.raises(ValueError, match="overlap.*smaller than.*chunk_size"):
            ConcreteChunker(chunk_size=400, overlap=400)

    def test_initialization_fails_when_overlap_exceeds_chunk_size(self):
        """Test that initialization fails when overlap exceeds chunk_size."""
        with pytest.raises(ValueError, match="overlap.*smaller than.*chunk_size"):
            ConcreteChunker(chunk_size=400, overlap=500)

    def test_initialization_fails_with_zero_chunk_size(self):
        """Test that initialization fails with zero chunk_size."""
        with pytest.raises(ValueError, match= "'chunk_size' must be greater than 0 and 'overlap' must be at least 0 "):
            ConcreteChunker(chunk_size=0, overlap=-1)

    def test_initialization_fails_with_negative_chunk_size(self):
        """Test that initialization fails with negative chunk_size."""
        with pytest.raises(ValueError, match= "'overlap' must be smaller than 'chunk_size'."):
            ConcreteChunker(chunk_size=-100, overlap=50)

    def test_initialization_fails_with_negative_overlap(self):
        """Test that initialization fails with negative overlap."""
        with pytest.raises(ValueError, match="'chunk_size' must be greater than 0 and 'overlap' must be at least 0 "):
            ConcreteChunker(chunk_size=400, overlap=-10)

    def test_chunk_size_property_getter(self):
        """Test chunk_size property getter."""
        chunker = ConcreteChunker(chunk_size=500)
        assert chunker.chunk_size == 500

    def test_chunk_size_property_setter(self):
        """Test chunk_size property setter with valid value."""
        chunker = ConcreteChunker(chunk_size=400, overlap=100)
        chunker.chunk_size = 600
        assert chunker.chunk_size == 600

    def test_chunk_size_setter_fails_when_less_than_overlap(self):
        """Test chunk_size setter fails when new value is less than overlap."""
        chunker = ConcreteChunker(chunk_size=400, overlap=200)

        with pytest.raises(ValueError, match="overlap.*smaller than.*chunk_size"):
            chunker.chunk_size = 100

    def test_overlap_property_getter(self):
        """Test overlap property getter."""
        chunker = ConcreteChunker(overlap=150)
        assert chunker.overlap == 150

    def test_overlap_property_setter(self):
        """Test overlap property setter with valid value."""
        chunker = ConcreteChunker(chunk_size=400, overlap=100)
        chunker.overlap = 150
        assert chunker.overlap == 150

    def test_overlap_setter_fails_when_exceeds_chunk_size(self):
        """Test overlap setter fails when new value exceeds chunk_size."""
        chunker = ConcreteChunker(chunk_size=400, overlap=100)

        with pytest.raises(ValueError, match="overlap.*smaller than.*chunk_size"):
            chunker.overlap = 500

    def test_overlap_setter_fails_when_negative(self):
        """Test overlap setter fails when negative."""
        chunker = ConcreteChunker(chunk_size=400, overlap=100)

        with pytest.raises(ValueError, match="overlap.*at least 0"):
            chunker.overlap = -1

    def test_chunk_method_basic(self):
        """Test basic chunk method functionality."""
        chunker = ConcreteChunker()
        text = "line1\nline2\nline3"

        chunks = chunker.chunk(text)

        assert len(chunks) == 3
        assert all(isinstance(c, Chunk) for c in chunks)
        assert [c.content for c in chunks] == ["line1", "line2", "line3"]

    def test_chunk_method_with_document(self):
        """Test chunk method with document parameter."""
        chunker = ConcreteChunker()
        text = "line1\nline2"

        chunks = chunker.chunk(text, document="test-doc")

        assert all(c.document == "test-doc" for c in chunks)

    def test_chunk_method_with_metadata(self):
        """Test chunk method with metadata parameter."""
        chunker = ConcreteChunker()
        text = "line1\nline2"
        metadata = {"source": "test", "page": 1}

        chunks = chunker.chunk(text, metadata=metadata)

        assert all(c.metadata == metadata for c in chunks)

    def test_chunk_method_with_empty_text(self):
        """Test chunk method with empty text."""
        chunker = ConcreteChunker()

        chunks = chunker.chunk("")

        # "" .split('\n') -> [""] so you get a single empty chunk
        assert len(chunks) == 1
        assert chunks[0].content == ""

    @patch.object(MediaParser, "get_text")
    def test_chunk_from_file(self, mock_get_text):
        """Test chunk_from_file method."""
        mock_get_text.return_value = "line1\nline2\nline3"
        chunker = ConcreteChunker()

        chunks = chunker.chunk_from_file("test.txt")

        mock_get_text.assert_called_once_with("test.txt", encoding=None)
        assert len(chunks) == 3

    @patch.object(MediaParser, "get_text")
    def test_chunk_from_file_with_encoding(self, mock_get_text):
        """Test chunk_from_file with custom encoding."""
        mock_get_text.return_value = "content"
        chunker = ConcreteChunker()

        _ = chunker.chunk_from_file("test.txt", encoding="utf-8")

        mock_get_text.assert_called_once_with("test.txt", encoding="utf-8")

    @patch.object(MediaParser, "get_text")
    def test_chunk_from_file_with_document_and_metadata(self, mock_get_text):
        """Test chunk_from_file with document and metadata."""
        mock_get_text.return_value = "line1\nline2"
        chunker = ConcreteChunker()
        metadata = {"key": "value"}

        chunks = chunker.chunk_from_file(
            "test.txt",
            document="doc-id",
            metadata=metadata,
        )

        assert all(c.document == "doc-id" for c in chunks)
        assert all(c.metadata == metadata for c in chunks)

    def test_make_into_chunks(self):
        """Test make_into_chunks method."""
        chunker = ConcreteChunker()
        text_list = ["chunk1", "chunk2", "chunk3"]

        chunks = chunker.make_into_chunks(text_list)

        assert len(chunks) == 3
        assert all(isinstance(c, Chunk) for c in chunks)
        assert [c.content for c in chunks] == text_list

    def test_make_into_chunks_with_metadata(self):
        """Test make_into_chunks with metadata."""
        chunker = ConcreteChunker()
        text_list = ["chunk1", "chunk2"]
        metadata = {"test": "data"}

        chunks = chunker.make_into_chunks(
            text_list,
            document="doc",
            metadata=metadata,
        )

        assert all(c.metadata == metadata for c in chunks)
        assert all(c.document == "doc" for c in chunks)

    def test_make_into_chunks_copies_metadata_per_chunk(self):
        """
        If make_into_chunks copies metadata, mutating one chunk's metadata
        should not affect others.
        """
        chunker = ConcreteChunker()
        text_list = ["a", "b"]
        metadata = {"page": 1}

        chunks = chunker.make_into_chunks(text_list, metadata=metadata)

        assert len(chunks) == 2
        chunks[0].metadata["new_key"] = "value"
        # If you implemented copying, this should only appear in the first chunk
        assert "new_key" in chunks[0].metadata
        assert "new_key" not in chunks[1].metadata
        # And the original metadata dict should be untouched
        assert "new_key" not in metadata
