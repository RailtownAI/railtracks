"""
Unit tests for the LORAG core module.
"""

import os
import unittest
from unittest.mock import patch, MagicMock, mock_open
import tempfile
import json
import numpy as np

# Import the modules to test
from lorag.database import ChunkDatabase, FileDatabase
from lorag.core import LORAG


class TestLORAG(unittest.TestCase):
    """Test cases for the LORAG class."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary directory for test databases
        self.temp_dir = tempfile.mkdtemp()
        self.chunk_db_path = os.path.join(self.temp_dir, "chunks.db")
        self.file_db_path = os.path.join(self.temp_dir, "files.db")
        
        # Mock API key
        self.api_key = "test_api_key"
        
        # Create patch for OpenAI client
        self.openai_patcher = patch('openai.OpenAI')
        self.mock_openai = self.openai_patcher.start()
        
        # Mock embedding response
        self.mock_embedding_response = MagicMock()
        self.mock_embedding_response.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]
        
        # Mock chat completion response
        self.mock_chat_response = MagicMock()
        self.mock_chat_response.choices = [MagicMock(message=MagicMock(content="Test summary"))]
        
        # Configure mock OpenAI client
        self.mock_client = MagicMock()
        self.mock_client.embeddings.create.return_value = self.mock_embedding_response
        self.mock_client.chat.completions.create.return_value = self.mock_chat_response
        self.mock_openai.return_value = self.mock_client
        
        # Initialize LORAG with mock client
        self.lorag = LORAG(
            api_key=self.api_key,
            chunk_db_path=self.chunk_db_path,
            file_db_path=self.file_db_path
        )
    
    def tearDown(self):
        """Clean up after tests."""
        # Stop patchers
        self.openai_patcher.stop()
        
        # Remove temporary files
        if os.path.exists(self.chunk_db_path):
            os.remove(self.chunk_db_path)
        if os.path.exists(self.file_db_path):
            os.remove(self.file_db_path)
        os.rmdir(self.temp_dir)
    
    def test_initialization(self):
        """Test LORAG initialization."""
        self.assertEqual(self.lorag.api_key, self.api_key)
        self.assertEqual(self.lorag.chunk_db.db_path, self.chunk_db_path)
        self.assertEqual(self.lorag.file_db.db_path, self.file_db_path)
        self.assertIsNotNone(self.lorag.embedding_manager)
        self.assertIsNotNone(self.lorag.text_processor)
        self.assertIsNotNone(self.lorag.search_engine)
        self.assertIsNotNone(self.lorag.batch_processor)
    
    def test_get_embedding(self):
        """Test getting embeddings."""
        # Call the method
        embedding = self.lorag.get_embedding("Test text")
        
        # Verify the result
        self.assertEqual(embedding, [0.1, 0.2, 0.3])
        
        # Verify the API call
        self.mock_client.embeddings.create.assert_called_once()
        call_args = self.mock_client.embeddings.create.call_args[1]
        self.assertEqual(call_args["input"], "Test text")
    
    @patch('builtins.open', new_callable=mock_open, read_data="Test file content")
    @patch('os.path.isfile', return_value=True)
    def test_add_file(self, mock_isfile, mock_file):
        """Test adding a file."""
        # Mock the add_text method
        self.lorag.add_text = MagicMock(return_value={"file_id": 1, "status": "added"})
        
        # Call the method
        result = self.lorag.add_file("test_file.txt")
        
        # Verify the result
        self.assertEqual(result["file_id"], 1)
        self.assertEqual(result["status"], "added")
        
        # Verify the method calls
        mock_isfile.assert_called_once_with("test_file.txt")
        mock_file.assert_called_once_with("test_file.txt", 'r', encoding='utf-8')
        self.lorag.add_text.assert_called_once()
    
    @patch('os.path.isfile', return_value=False)
    def test_add_file_not_found(self, mock_isfile):
        """Test adding a non-existent file."""
        # Call the method and expect an exception
        with self.assertRaises(FileNotFoundError):
            self.lorag.add_file("nonexistent_file.txt")
        
        # Verify the method calls
        mock_isfile.assert_called_once_with("nonexistent_file.txt")
    
    def test_add_text_new(self):
        """Test adding new text."""
        # Mock database methods
        self.lorag.file_db.get_file_by_name = MagicMock(side_effect=ValueError("File not found"))
        self.lorag.file_db.add_file = MagicMock(return_value=1)
        self.lorag.chunk_db.add_chunk = MagicMock(return_value=1)
        self.lorag.text_processor.generate_summary = MagicMock(return_value="Test summary")
        self.lorag.text_processor.chunk_text = MagicMock(return_value=["Chunk 1", "Chunk 2"])
        self.lorag.embedding_manager.get_embedding = MagicMock(return_value=[0.1, 0.2, 0.3])
        
        # Call the method
        result = self.lorag.add_text("Test content", "test_name")
        
        # Verify the result
        self.assertEqual(result["file_id"], 1)
        self.assertEqual(result["status"], "added")
        self.assertEqual(result["file_name"], "test_name")
        self.assertEqual(result["chunks"]["total"], 2)
        self.assertEqual(result["chunks"]["added"], 2)
        
        # Verify the method calls
        self.lorag.file_db.get_file_by_name.assert_called_once_with("test_name")
        self.lorag.file_db.add_file.assert_called_once()
        self.assertEqual(self.lorag.chunk_db.add_chunk.call_count, 2)
    
    def test_add_text_existing(self):
        """Test adding existing text without force update."""
        # Mock database methods
        self.lorag.file_db.get_file_by_name = MagicMock(return_value={"id": 1})
        
        # Call the method
        result = self.lorag.add_text("Test content", "test_name", force_update=False)
        
        # Verify the result
        self.assertEqual(result["file_id"], 1)
        self.assertEqual(result["status"], "existing")
        self.assertEqual(result["file_name"], "test_name")
        
        # Verify the method calls
        self.lorag.file_db.get_file_by_name.assert_called_once_with("test_name")
    
    def test_search(self):
        """Test search functionality."""
        # Mock search engine
        self.lorag.search_engine.search = MagicMock(return_value={"results": ["result1", "result2"]})
        
        # Call the method
        result = self.lorag.search("test query", search_mode="all", n_return=5)
        
        # Verify the result
        self.assertEqual(result["results"], ["result1", "result2"])
        
        # Verify the method calls
        self.lorag.search_engine.search.assert_called_once_with(
            query="test query",
            search_mode="all",
            n_return=5,
            n_token=None,
            n_confidence=None,
            blacklist_file=None,
            effort=1,
            weights=None
        )


if __name__ == '__main__':
    unittest.main()