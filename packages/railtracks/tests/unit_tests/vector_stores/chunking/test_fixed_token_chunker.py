from railtracks.vector_stores import FixedTokenChunker, Chunk, MediaParser

from unittest.mock import patch


import tiktoken

class TestFixedTokenChunker:
    """Tests for the FixedTokenChunker implementation."""

    def test_initialization_default_tokenizer(self):
        """Test initialization with default tokenizer."""
        chunker = FixedTokenChunker()

        assert chunker.chunk_size == 400
        assert chunker.overlap == 200
        assert isinstance(chunker._tokenizer, tiktoken.Encoding)

    def test_initialization_custom_tokenizer(self):
        """Test initialization with custom tokenizer name."""
        chunker = FixedTokenChunker(tokenizer="cl100k_base")
        assert chunker._tokenizer.name == "cl100k_base"

    def test_initialization_with_custom_params(self):
        """Test initialization with custom chunk_size and overlap."""
        chunker = FixedTokenChunker(chunk_size=1000, overlap=100)

        assert chunker.chunk_size == 1000
        assert chunker.overlap == 100

    def test_split_text_simple(self):
        """Test split_text with simple text."""
        chunker = FixedTokenChunker(chunk_size=10, overlap=5)
        text = "This is a simple test sentence for token chunking."

        chunks = chunker.split_text(text)

        assert len(chunks) > 0
        assert all(isinstance(chunk, str) for chunk in chunks)

    def test_split_text_respects_chunk_size(self):
        """Test that split_text respects chunk_size limit."""
        chunker = FixedTokenChunker(chunk_size=5, overlap=0)
        text = "word " * 20  # 20 words, should create multiple chunks

        chunks = chunker.split_text(text)

        # Verify each chunk has at most chunk_size tokens
        for chunk in chunks:
            tokens = chunker._tokenizer.encode(chunk)
            assert len(tokens) <= 5

    def test_split_text_with_overlap(self):
        """Test that split_text creates overlapping chunks."""
        chunker = FixedTokenChunker(chunk_size=10, overlap=5)
        text = "word " * 30

        chunks = chunker.split_text(text)

        assert len(chunks) > 1

    def test_split_text_overlap_window_matches_expected_tokens(self):
        """
        More precise test: with overlap, windows should share exactly `overlap`
        tokens (when text is long enough).
        """
        chunker = FixedTokenChunker(chunk_size=8, overlap=3)
        text = " ".join(f"w{i}" for i in range(20))
        tokens = chunker._tokenizer.encode(text)

        chunks = chunker.split_text(text)
        encoded_chunks = [chunker._tokenizer.encode(c) for c in chunks]

        # Only check for pairs where both chunks are full-sized
        for i in range(len(encoded_chunks) - 1):
            a = encoded_chunks[i]
            b = encoded_chunks[i + 1]
            if len(a) >= 8 and len(b) >= 8:
                assert a[-3:] == b[:3]

    def test_split_text_empty_string(self):
        """Test split_text with empty string."""
        chunker = FixedTokenChunker()

        chunks = chunker.split_text("")

        assert chunks == []

    def test_split_text_single_token(self):
        """Test split_text with single token."""
        chunker = FixedTokenChunker(chunk_size=10, overlap=0)

        chunks = chunker.split_text("Hi")

        assert len(chunks) == 1
        assert chunks[0] == "Hi"

    def test_split_text_exact_chunk_size(self):
        """Test split_text when text is exactly chunk_size tokens."""
        chunk_size = 5
        chunker = FixedTokenChunker(chunk_size=chunk_size, overlap=0)
        text = "One two three four five"
        tokens = chunker._tokenizer.encode(text)

        chunks = chunker.split_text(text)
        assert len(chunks) == len(tokens)/chunk_size

    def test_chunk_method_creates_chunk_objects(self):
        """Test that chunk method creates Chunk objects."""
        chunker = FixedTokenChunker(chunk_size=10, overlap=5)
        text = "This is a test sentence that will be chunked."

        chunks = chunker.chunk(text)

        assert all(isinstance(chunk, Chunk) for chunk in chunks)
        assert all(chunk.id is not None for chunk in chunks)

    def test_chunk_method_with_metadata(self):
        """Test chunk method preserves metadata reference."""
        chunker = FixedTokenChunker(chunk_size=10, overlap=5)
        text = "Test content"
        metadata = {"source": "test"}

        chunks = chunker.chunk(text, metadata=metadata)

        metadata["source"] = "failed_test"

        assert len(chunks) >= 1
        assert all(chunk.metadata["source"] != metadata["source"] for chunk in chunks)

    def test_chunk_unicode_text(self):
        """Test chunking with unicode characters."""
        chunker = FixedTokenChunker(chunk_size=20, overlap=5)
        text = "Hello 世界! This is a test with émojis 🎉 and spëcial çharacters."

        chunks = chunker.chunk(text)

        assert len(chunks) > 0
        assert all(isinstance(chunk.content, str) for chunk in chunks)

    def test_chunk_very_long_text(self):
        """Test chunking very long text."""
        chunker = FixedTokenChunker(chunk_size=50, overlap=10)
        text = "word " * 1000

        chunks = chunker.chunk(text)

        assert len(chunks) > 1
        assert all(isinstance(chunk, Chunk) for chunk in chunks)

    def test_no_overlap_produces_contiguous_chunks(self):
        """Test that zero overlap produces non-overlapping chunks."""
        chunker = FixedTokenChunker(chunk_size=5, overlap=0)
        text = "one two three four five six seven eight nine ten"

        chunks = chunker.split_text(text)

        total_tokens = sum(len(chunker._tokenizer.encode(c)) for c in chunks)
        original_tokens = len(chunker._tokenizer.encode(text))

        # Total tokens should match exactly with zero overlap
        assert total_tokens == original_tokens

    @patch.object(MediaParser, "get_text")
    def test_chunk_from_file_integration(self, mock_get_text):
        """Test chunk_from_file method integration."""
        mock_get_text.return_value = "This is test content from a file."
        chunker = FixedTokenChunker(chunk_size=10, overlap=5)

        chunks = chunker.chunk_from_file("test.txt")

        mock_get_text.assert_called_once_with("test.txt", encoding=None)
        assert len(chunks) > 0
        assert all(isinstance(chunk, Chunk) for chunk in chunks)
