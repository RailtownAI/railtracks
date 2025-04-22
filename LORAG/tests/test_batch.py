import os
import json
import pytest
from unittest.mock import MagicMock, patch
from lorag.batch import BatchProcessor

# test_batch.py


@pytest.fixture
def mock_batch_processor():
    """Fixture to create a mocked BatchProcessor instance."""
    with patch("lorag.batch.EmbeddingManager") as MockEmbeddingManager, \
         patch("lorag.batch.ChunkDatabase") as MockChunkDatabase, \
         patch("lorag.batch.FileDatabase") as MockFileDatabase, \
         patch("lorag.batch.OpenAI") as MockOpenAI:
        
        MockEmbeddingManager.return_value = MagicMock()
        MockChunkDatabase.return_value = MagicMock()
        MockFileDatabase.return_value = MagicMock()
        MockOpenAI.return_value = MagicMock()
        
        processor = BatchProcessor(api_key="test_api_key")
        return processor

def test_init(mock_batch_processor):
    """Test initialization of BatchProcessor."""
    assert mock_batch_processor.api_key == "test_api_key"
    assert mock_batch_processor.chunk_db is not None
    assert mock_batch_processor.file_db is not None
    assert mock_batch_processor.embedding_manager is not None
    assert mock_batch_processor.client is not None

def test_chunk_text(mock_batch_processor):
    """Test _chunk_text method."""
    text = "This is a test text for chunking."
    chunks = mock_batch_processor._chunk_text(text, chunk_size=10, chunk_overlap=5)
    assert chunks == ["This is a ", "test text ", "for chunki", "ng."]

def test_chunk_text_token(mock_batch_processor):
    """Test _chunk_text_token method."""
    mock_tokenizer = MagicMock()
    mock_tokenizer.encode.return_value = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    mock_tokenizer.decode.side_effect = lambda tokens: " ".join(map(str, tokens))
    
    with patch("lorag.batch.LORAGTokenizer", return_value=mock_tokenizer):
        chunks = mock_batch_processor._chunk_text_token("test text", chunk_size=4, chunk_overlap=2)
        assert chunks == ["1 2 3 4", "3 4 5 6", "5 6 7 8", "7 8 9 10"]

def test_prepare_batch_embeddings(mock_batch_processor, tmp_path):
    """Test prepare_batch_embeddings method."""
    texts = [{"name": "doc1", "content": "This is a test document."}]
    output_file = os.path.join(tmp_path, "batch_embeddings.jsonl")
    
    mock_batch_processor.file_db.file_exists.return_value = False
    result_file = mock_batch_processor.prepare_batch_embeddings(texts, output_file)
    
    assert result_file == output_file
    with open(result_file, "r") as f:
        lines = f.readlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["custom_id"] == "doc1"
        assert data["content"] == "This is a test document."

def test_prepare_batch_summaries(mock_batch_processor, tmp_path):
    """Test prepare_batch_summaries method."""
    texts = [{"name": "doc1", "content": "This is a test document."}]
    output_file = os.path.join(tmp_path, "batch_summaries.jsonl")
    
    result_file = mock_batch_processor.prepare_batch_summaries(texts, output_file)
    
    assert result_file == output_file
    with open(result_file, "r") as f:
        lines = f.readlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["custom_id"] == "doc1"
        assert "messages" in data["body"]

def test_process_batch_embeddings(mock_batch_processor, tmp_path):
    """Test process_batch_embeddings method."""
    batch_file = os.path.join(tmp_path, "batch_embeddings.jsonl")
    output_file = os.path.join(tmp_path, "batch_embeddings_results.jsonl")
    
    with open(batch_file, "w") as f:
        f.write(json.dumps({"custom_id": "doc1", "content": "test content"}) + "\n")
    
    mock_batch_processor.embedding_manager.get_embedding_batch.return_value = {
        "request-1": [0.1, 0.2, 0.3]
    }
    
    stats = mock_batch_processor.process_batch_embeddings(batch_file, output_file)
    
    assert stats["total"] == 1
    assert stats["success"] == 1
    assert stats["error"] == 0
    with open(output_file, "r") as f:
        lines = f.readlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["custom_id"] == "doc1"
        assert data["embedding"] == [0.1, 0.2, 0.3]

def test_process_batch_summaries(mock_batch_processor, tmp_path):
    """Test process_batch_summaries method."""
    batch_file = os.path.join(tmp_path, "batch_summaries.jsonl")
    output_file = os.path.join(tmp_path, "batch_summaries_results.jsonl")
    
    with open(batch_file, "w") as f:
        f.write(json.dumps({
            "custom_id": "doc1",
            "body": {
                "messages": [{"role": "user", "content": "test content"}]
            }
        }) + "\n")
    
    mock_batch_processor.client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="Test summary"))]
    )
    
    stats = mock_batch_processor.process_batch_summaries(batch_file, output_file)
    
    assert stats["total"] == 1
    assert stats["success"] == 1
    assert stats["error"] == 0
    with open(output_file, "r") as f:
        lines = f.readlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["custom_id"] == "doc1"
        assert data["summary"] == "Test summary"

def test_add_texts_batch(mock_batch_processor):
    """Test add_texts_batch method."""
    texts = [{"name": "doc1", "content": "This is a test document."}]
    
    mock_batch_processor.prepare_batch_embeddings = MagicMock(return_value="batch_embeddings.jsonl")
    mock_batch_processor.process_batch_embeddings = MagicMock(return_value={"success": 1})
    mock_batch_processor.prepare_batch_summaries = MagicMock(return_value="batch_summaries.jsonl")
    mock_batch_processor.process_batch_summaries = MagicMock(return_value={"success": 1})
    mock_batch_processor.file_db.file_exists.return_value = False
    mock_batch_processor.file_db.add_file.return_value = 1
    
    result = mock_batch_processor.add_texts_batch(texts)
    
    assert result["stats"]["total"] == 1
    assert result["stats"]["new_embedded"] == 1
    assert result["stats"]["new_summarized"] == 1
    assert result["stats"]["existing"] == 0
    assert result["stats"]["skipped"] == 0