"""
Unit tests for the LORAG system.
"""

import os
import unittest
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from lorag import LORAG
from lorag.embedding_manager import EmbeddingManager
from lorag.text_processing import TextProcessor
from lorag.database import ChunkDatabase, FileDatabase

# Mock API key for testing
API_KEY = "sk-test-key"

# Create mock response classes
class MockEmbeddingResponse:
    class EmbeddingData:
        def __init__(self, embedding):
            self.embedding = embedding
    
    def __init__(self):
        self.data = [self.EmbeddingData([0.1] * 10)]

class MockCompletionResponse:
    class Choice:
        def __init__(self):
            self.message = MagicMock()
            self.message.content = "This is a mock summary."
    
    def __init__(self):
        self.choices = [self.Choice()]


class TestLORAG(unittest.TestCase):
    """Test cases for the LORAG system."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary directory for test data
        self.test_dir = tempfile.mkdtemp()
        self.chunk_db_path = os.path.join(self.test_dir, "chunks.db")
        self.file_db_path = os.path.join(self.test_dir, "files.db")
        
        # Create test files
        self.test_file_path = os.path.join(self.test_dir, "test.txt")
        with open(self.test_file_path, 'w') as f:
            f.write("This is a test file for LORAG.")
        
        # Set up patches
        self.embeddings_patch = patch('openai.resources.embeddings.Embeddings.create', 
                                     return_value=MockEmbeddingResponse())
        self.completions_patch = patch('openai.resources.chat.completions.Completions.create', 
                                      return_value=MockCompletionResponse())
        
        # Start patches
        self.mock_embeddings = self.embeddings_patch.start()
        self.mock_completions = self.completions_patch.start()
        
        # Initialize LORAG
        self.lorag = LORAG(API_KEY, self.chunk_db_path, self.file_db_path)
    
    def tearDown(self):
        """Clean up test environment."""
        # Remove temporary directory
        shutil.rmtree(self.test_dir)
        
        # Stop patches
        self.embeddings_patch.stop()
        self.completions_patch.stop()
    
    def test_embedding_manager(self):
        """Test EmbeddingManager."""
        embedding_manager = EmbeddingManager(API_KEY)
        embedding = embedding_manager.get_embedding("Test text")
        
        self.assertIsInstance(embedding, list)
        self.assertEqual(len(embedding), 10)  # Mock embedding has 10 elements
    
    def test_text_processor(self):
        """Test TextProcessor."""
        text_processor = TextProcessor(API_KEY)
        summary = text_processor.generate_summary("Test text")
        
        self.assertEqual(summary, "This is a mock summary.")
        
        chunks = text_processor.chunk_text("This is a test text.", 10, 5)
        # The actual chunking depends on the implementation, so we'll just check that we got chunks
        self.assertIsInstance(chunks, list)
        self.assertTrue(all(isinstance(chunk, str) for chunk in chunks))
        self.assertTrue(len(chunks) > 0)
    
    def test_add_file(self):
        """Test adding a file to LORAG."""
        file_id = self.lorag.add_file(self.test_file_path)
        
        self.assertIsInstance(file_id, int)
        self.assertGreater(file_id, 0)
        
        # Check if file was added to database
        file = self.lorag.file_db.get_file(file_id)
        self.assertEqual(file['name'], "test.txt")
        self.assertEqual(file['puretext'], "This is a test file for LORAG.")
    
    def test_add_text(self):
        """Test adding text to LORAG."""
        text = "This is a test text for LORAG."
        name = "test_text"
        
        file_id = self.lorag.add_text(text, name)
        
        self.assertIsInstance(file_id, int)
        self.assertGreater(file_id, 0)
        
        # Check if text was added to database
        file = self.lorag.file_db.get_file(file_id)
        self.assertEqual(file['name'], name)
        self.assertEqual(file['puretext'], text)
    
    @patch('lorag.search_engine.SearchEngine.search')
    def test_search(self, mock_search):
        """Test searching in LORAG."""
        # Mock search results
        mock_search.return_value = {
            'results': [
                {
                    'file_name': 'python_text',
                    'content': 'This is a test text about Python programming.',
                    'weighted_score': 0.8
                }
            ],
            'confidence': {'python_text': 0.9},
            'methods_used': ['embedding', 'file_name_lookup']
        }
        
        # Search for text
        results = self.lorag.search("Python", search_mode="all", n_return=1)
        
        # Verify search was called
        mock_search.assert_called_once()
        
        # Check results
        self.assertIn('results', results)
        self.assertEqual(len(results['results']), 1)
        self.assertEqual(results['results'][0]['file_name'], 'python_text')


if __name__ == '__main__':
    unittest.main()