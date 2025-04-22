"""
Unit tests for the LORAG database module.
"""

import os
import unittest
import tempfile
import json
import numpy as np
import sqlite3

# Import the module to test
from lorag.database import BaseDatabase, ChunkDatabase, FileDatabase, count_tokens


class TestBaseDatabase(unittest.TestCase):
    """Test cases for the BaseDatabase class."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a temporary file for the test database
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.db_path = self.temp_file.name
        self.temp_file.close()
        
        # Create a test subclass of BaseDatabase
        class TestDatabase(BaseDatabase):
            def _create_tables(self):
                conn = self._connect()
                cursor = conn.cursor()
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS test_table (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    embedding BLOB
                )
                ''')
                conn.commit()
                conn.close()
            
            def _get_table_name(self):
                return "test_table"
            
            def _process_row(self, row):
                if not row:
                    return None
                
                item = dict(row)
                if item['embedding']:
                    item['embedding'] = self._blob_to_embedding(item['embedding'])
                return item
        
        # Initialize the test database
        self.db = TestDatabase(self.db_path)
    
    def tearDown(self):
        """Clean up after tests."""
        # Remove the temporary database file
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
    
    def test_embedding_conversion(self):
        """Test embedding conversion methods."""
        # Create a test embedding
        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        
        # Convert to blob and back
        blob = self.db._embedding_to_blob(embedding)
        result = self.db._blob_to_embedding(blob)
        
        # Verify the result
        self.assertEqual(len(result), len(embedding))
        for i in range(len(embedding)):
            self.assertAlmostEqual(result[i], embedding[i], places=6)
    
    def test_connect(self):
        """Test database connection."""
        # Connect to the database
        conn = self.db._connect()
        
        # Verify the connection
        self.assertIsInstance(conn, sqlite3.Connection)
        
        # Close the connection
        conn.close()


class TestChunkDatabase(unittest.TestCase):
    """Test cases for the ChunkDatabase class."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a temporary file for the test database
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.db_path = self.temp_file.name
        self.temp_file.close()
        
        # Initialize the chunk database
        self.db = ChunkDatabase(self.db_path)
    
    def tearDown(self):
        """Clean up after tests."""
        # Remove the temporary database file
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
    
    def test_add_and_get_chunk(self):
        """Test adding and retrieving a chunk."""
        # Add a test chunk
        chunk_id = self.db.add_chunk(
            chunk_name="test_file:1",
            file_id=1,
            puretext="Test chunk content",
            tags=["tag1", "tag2"],
            summary="Test summary",
            embedding=[0.1, 0.2, 0.3],
            file_name_embedding=[0.4, 0.5, 0.6]
        )
        
        # Verify the chunk ID
        self.assertIsNotNone(chunk_id)
        self.assertGreater(chunk_id, 0)
        
        # Get the chunk
        chunk = self.db.get_chunk(chunk_id)
        
        # Verify the chunk data
        self.assertEqual(chunk["chunk_name"], "test_file:1")
        self.assertEqual(chunk["file_id"], 1)
        self.assertEqual(chunk["puretext"], "Test chunk content")
        self.assertEqual(chunk["tags"], ["tag1", "tag2"])
        self.assertEqual(chunk["summary"], "Test summary")
        self.assertEqual(len(chunk["embedding"]), 3)
        self.assertEqual(len(chunk["file_name_embedding"]), 3)
    
    def test_chunk_exists(self):
        """Test checking if a chunk exists."""
        # Add a test chunk
        self.db.add_chunk(
            chunk_name="test_file:1",
            file_id=1,
            puretext="Test chunk content"
        )
        
        # Check if the chunk exists
        self.assertTrue(self.db.chunk_exists("test_file:1"))
        self.assertFalse(self.db.chunk_exists("nonexistent_chunk"))
    
    def test_get_chunks_by_file_id(self):
        """Test getting chunks by file ID."""
        # Add test chunks
        self.db.add_chunk(
            chunk_name="test_file:1",
            file_id=1,
            puretext="Test chunk 1"
        )
        self.db.add_chunk(
            chunk_name="test_file:2",
            file_id=1,
            puretext="Test chunk 2"
        )
        self.db.add_chunk(
            chunk_name="other_file:1",
            file_id=2,
            puretext="Other chunk"
        )
        
        # Get chunks by file ID
        chunks = self.db.get_chunks_by_file_id(1)
        
        # Verify the chunks
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0]["chunk_name"], "test_file:1")
        self.assertEqual(chunks[1]["chunk_name"], "test_file:2")
    
    def test_update_chunk(self):
        """Test updating a chunk."""
        # Add a test chunk
        chunk_id = self.db.add_chunk(
            chunk_name="test_file:1",
            file_id=1,
            puretext="Test chunk content",
            tags=["tag1"]
        )
        
        # Update the chunk
        success = self.db.update_chunk(
            chunk_id,
            puretext="Updated content",
            tags=["tag1", "tag2"],
            summary="New summary"
        )
        
        # Verify the update
        self.assertTrue(success)
        
        # Get the updated chunk
        chunk = self.db.get_chunk(chunk_id)
        
        # Verify the chunk data
        self.assertEqual(chunk["puretext"], "Updated content")
        self.assertEqual(chunk["tags"], ["tag1", "tag2"])
        self.assertEqual(chunk["summary"], "New summary")
    
    def test_delete_chunk(self):
        """Test deleting a chunk."""
        # Add a test chunk
        chunk_id = self.db.add_chunk(
            chunk_name="test_file:1",
            file_id=1,
            puretext="Test chunk content"
        )
        
        # Delete the chunk
        success = self.db.delete_chunk(chunk_id)
        
        # Verify the deletion
        self.assertTrue(success)
        
        # Try to get the deleted chunk
        chunk = self.db.get_chunk(chunk_id)
        
        # Verify the chunk is gone
        self.assertIsNone(chunk)
    
    def test_search_by_embedding(self):
        """Test searching by embedding similarity."""
        # Add test chunks with embeddings
        self.db.add_chunk(
            chunk_name="test_file:1",
            file_id=1,
            puretext="Test chunk 1",
            embedding=[0.9, 0.1, 0.1]  # More similar to query
        )
        self.db.add_chunk(
            chunk_name="test_file:2",
            file_id=1,
            puretext="Test chunk 2",
            embedding=[0.1, 0.9, 0.1]  # Less similar to query
        )
        
        # Search by embedding
        query_embedding = [1.0, 0.0, 0.0]
        results = self.db.search_by_embedding(query_embedding, top_n=2)
        
        # Verify the results
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["chunk"]["chunk_name"], "test_file:1")
        self.assertEqual(results[1]["chunk"]["chunk_name"], "test_file:2")
        self.assertGreater(results[0]["similarity"], results[1]["similarity"])


class TestFileDatabase(unittest.TestCase):
    """Test cases for the FileDatabase class."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a temporary file for the test database
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.db_path = self.temp_file.name
        self.temp_file.close()
        
        # Initialize the file database
        self.db = FileDatabase(self.db_path)
    
    def tearDown(self):
        """Clean up after tests."""
        # Remove the temporary database file
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
    
    def test_add_and_get_file(self):
        """Test adding and retrieving a file."""
        # Add a test file
        file_id = self.db.add_file(
            name="test_file",
            file_path="/path/to/test_file",
            puretext="Test file content",
            tags=["tag1", "tag2"],
            summary="Test summary",
            embedding=[0.1, 0.2, 0.3],
            file_name_embedding=[0.4, 0.5, 0.6]
        )
        
        # Verify the file ID
        self.assertIsNotNone(file_id)
        self.assertGreater(file_id, 0)
        
        # Get the file
        file = self.db.get_file(file_id)
        
        # Verify the file data
        self.assertEqual(file["name"], "test_file")
        self.assertEqual(file["file_path"], "/path/to/test_file")
        self.assertEqual(file["puretext"], "Test file content")
        self.assertEqual(file["tags"], ["tag1", "tag2"])
        self.assertEqual(file["summary"], "Test summary")
        self.assertEqual(len(file["embedding"]), 3)
        self.assertEqual(len(file["file_name_embedding"]), 3)
    
    def test_file_exists(self):
        """Test checking if a file exists."""
        # Add a test file
        self.db.add_file(
            name="test_file",
            file_path="/path/to/test_file",
            puretext="Test file content"
        )
        
        # Check if the file exists
        self.assertTrue(self.db.file_exists("test_file"))
        self.assertFalse(self.db.file_exists("nonexistent_file"))
    
    def test_get_file_id(self):
        """Test getting a file ID by name."""
        # Add a test file
        file_id = self.db.add_file(
            name="test_file",
            file_path="/path/to/test_file",
            puretext="Test file content"
        )
        
        # Get the file ID
        result_id = self.db.get_file_id("test_file")
        
        # Verify the file ID
        self.assertEqual(result_id, file_id)
        
        # Try to get a nonexistent file ID
        result_id = self.db.get_file_id("nonexistent_file")
        
        # Verify the result
        self.assertIsNone(result_id)
    
    def test_get_file_by_name(self):
        """Test getting a file by name."""
        # Add a test file
        self.db.add_file(
            name="test_file",
            file_path="/path/to/test_file",
            puretext="Test file content"
        )
        
        # Get the file by name
        file = self.db.get_file_by_name("test_file")
        
        # Verify the file data
        self.assertEqual(file["name"], "test_file")
        self.assertEqual(file["file_path"], "/path/to/test_file")
        self.assertEqual(file["puretext"], "Test file content")
    
    def test_get_file_by_path(self):
        """Test getting a file by path."""
        # Add a test file
        self.db.add_file(
            name="test_file",
            file_path="/path/to/test_file",
            puretext="Test file content"
        )
        
        # Get the file by path
        file = self.db.get_file_by_path("/path/to/test_file")
        
        # Verify the file data
        self.assertEqual(file["name"], "test_file")
        self.assertEqual(file["file_path"], "/path/to/test_file")
        self.assertEqual(file["puretext"], "Test file content")
    
    def test_update_file(self):
        """Test updating a file."""
        # Add a test file
        file_id = self.db.add_file(
            name="test_file",
            file_path="/path/to/test_file",
            puretext="Test file content",
            tags=["tag1"]
        )
        
        # Update the file
        success = self.db.update_file(
            file_id,
            puretext="Updated content",
            tags=["tag1", "tag2"],
            summary="New summary"
        )
        
        # Verify the update
        self.assertTrue(success)
        
        # Get the updated file
        file = self.db.get_file(file_id)
        
        # Verify the file data
        self.assertEqual(file["puretext"], "Updated content")
        self.assertEqual(file["tags"], ["tag1", "tag2"])
        self.assertEqual(file["summary"], "New summary")
    
    def test_delete_file(self):
        """Test deleting a file."""
        # Add a test file
        file_id = self.db.add_file(
            name="test_file",
            file_path="/path/to/test_file",
            puretext="Test file content"
        )
        
        # Delete the file
        success = self.db.delete_file(file_id)
        
        # Verify the deletion
        self.assertTrue(success)
        
        # Try to get the deleted file
        file = self.db.get_file(file_id)
        
        # Verify the file is gone
        self.assertIsNone(file)
    
    def test_search_by_embedding(self):
        """Test searching by embedding similarity."""
        # Add test files with embeddings
        self.db.add_file(
            name="test_file_1",
            file_path="/path/to/test_file_1",
            puretext="Test file 1",
            embedding=[0.9, 0.1, 0.1]  # More similar to query
        )
        self.db.add_file(
            name="test_file_2",
            file_path="/path/to/test_file_2",
            puretext="Test file 2",
            embedding=[0.1, 0.9, 0.1]  # Less similar to query
        )
        
        # Search by embedding
        query_embedding = [1.0, 0.0, 0.0]
        results = self.db.search_by_embedding(query_embedding, top_n=2)
        
        # Verify the results
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["file"]["name"], "test_file_1")
        self.assertEqual(results[1]["file"]["name"], "test_file_2")
        self.assertGreater(results[0]["similarity"], results[1]["similarity"])


class TestUtilityFunctions(unittest.TestCase):
    """Test cases for utility functions."""
    
    def test_count_tokens(self):
        """Test token counting function."""
        # Count tokens in a simple text
        text = "This is a test."
        count = count_tokens(text)
        
        # Verify the count is reasonable
        self.assertGreater(count, 0)
        self.assertLess(count, 10)  # Should be around 4-5 tokens


if __name__ == '__main__':
    unittest.main()