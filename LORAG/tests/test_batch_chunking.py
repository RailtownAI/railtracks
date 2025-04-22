import pytest
from unittest.mock import patch
from lorag.batch import BatchProcessor

@pytest.fixture
def batch_processor():
    """Fixture to create a BatchProcessor instance."""
    return BatchProcessor(api_key="dummy_api_key")

@patch("lorag.batch.tiktoken.get_encoding")
def test_chunk_text_token_basic(mock_get_encoding, batch_processor):
    """Test basic functionality of _chunk_text_token."""
    # Mock tokenizer
    mock_tokenizer = mock_get_encoding.return_value
    mock_tokenizer.encode.return_value = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    mock_tokenizer.decode.side_effect = lambda tokens: " ".join(map(str, tokens))

    text = "dummy text"
    chunk_size = 4
    chunk_overlap = 2

    chunks = batch_processor._chunk_text_token(text, chunk_size, chunk_overlap)

    assert chunks == ["1 2 3 4", "3 4 5 6", "5 6 7 8", "7 8 9 10"]
    mock_get_encoding.assert_called_once_with("cl100k_base")
    mock_tokenizer.encode.assert_called_once_with(text)

@patch("lorag.batch.tiktoken.get_encoding")
def test_chunk_text_token_edge_case(mock_get_encoding, batch_processor):
    """Test edge case where text is shorter than chunk size."""
    # Mock tokenizer
    mock_tokenizer = mock_get_encoding.return_value
    mock_tokenizer.encode.return_value = [1, 2, 3]
    mock_tokenizer.decode.side_effect = lambda tokens: " ".join(map(str, tokens))

    text = "short text"
    chunk_size = 10
    chunk_overlap = 5

    chunks = batch_processor._chunk_text_token(text, chunk_size, chunk_overlap)

    assert chunks == ["1 2 3"]
    mock_get_encoding.assert_called_once_with("cl100k_base")
    mock_tokenizer.encode.assert_called_once_with(text)

@patch("lorag.batch.tiktoken.get_encoding")
def test_chunk_text_token_overlap(mock_get_encoding, batch_processor):
    """Test functionality with overlap greater than chunk size."""
    # Mock tokenizer
    mock_tokenizer = mock_get_encoding.return_value
    mock_tokenizer.encode.return_value = [1, 2, 3, 4, 5]
    mock_tokenizer.decode.side_effect = lambda tokens: " ".join(map(str, tokens))

    text = "overlap test"
    chunk_size = 3
    chunk_overlap = 4
    try:
        chunks = batch_processor._chunk_text_token(text, chunk_size, chunk_overlap)
    # assert expeption
    except ValueError as e:
        assert str(e)
    