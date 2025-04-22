"""
Database module for LORAG system.
Contains classes for managing chunk and file databases.
"""

import os
import json
import sqlite3
import numpy as np
import csv
from typing import List, Dict, Any, Optional, Union, Tuple, Set
import tiktoken


class BaseDatabase:
    """Base class for database operations."""
    
    def __init__(self, db_path: str):
        """Initialize the database.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._create_tables()
    
    def _create_tables(self):
        """Create necessary tables if they don't exist."""
        raise NotImplementedError("Subclasses must implement this method")
    
    def _connect(self):
        """Connect to the database."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _embedding_to_blob(self, embedding: List[float]) -> bytes:
        """Convert embedding list to binary blob for storage."""
        return np.array(embedding, dtype=np.float32).tobytes()
    
    def _blob_to_embedding(self, blob: bytes) -> List[float]:
        """Convert binary blob to embedding list."""
        return np.frombuffer(blob, dtype=np.float32).tolist()
    
    def _process_row(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Process a database row into a dictionary with proper types."""
        raise NotImplementedError("Subclasses must implement this method")
    
    def export_to_csv(self, csv_path: str, blacklist: Optional[List[str]] = None):
        """Export database table to CSV, excluding blacklisted columns.
        
        Args:
            csv_path: Path where the CSV file will be saved.
            blacklist: List of column names to exclude from the CSV.
        """
        blacklist_set = set(blacklist) if blacklist else set()
        
        conn = self._connect()
        cursor = conn.cursor()
        
        # Get table name from subclass
        table_name = self._get_table_name()
        
        # Retrieve column names
        cursor.execute(f'SELECT * FROM {table_name} LIMIT 0')
        column_names = [description[0] for description in cursor.description]
        
        # Filter out blacklisted columns
        filtered_columns = [name for name in column_names if name not in blacklist_set]
        
        # Fetch data
        rows = cursor.execute(f'SELECT {", ".join(filtered_columns)} FROM {table_name}').fetchall()
        
        conn.close()
        
        # Write to CSV
        with open(csv_path, mode='w', newline='', encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(filtered_columns)  # Write headers
            writer.writerows(rows)  # Write data
    
    def _get_table_name(self) -> str:
        """Get the table name for this database."""
        raise NotImplementedError("Subclasses must implement this method")


class ChunkDatabase(BaseDatabase):
    """Database for storing and retrieving text chunks."""
    
    def __init__(self, db_path: str = "data/bright/index/chunks.db"):
        """Initialize the chunk database.
        
        Args:
            db_path: Path to the SQLite database file
        """
        super().__init__(db_path)
    
    def _get_table_name(self) -> str:
        """Get the table name for this database."""
        return "chunks"
    
    def _create_tables(self):
        """Create necessary tables if they don't exist."""
        conn = self._connect()
        cursor = conn.cursor()
        
        # Create chunks table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chunk_name TEXT NOT NULL,
            file_id INTEGER NOT NULL,
            tags TEXT,
            puretext TEXT NOT NULL,
            summary TEXT,
            embedding BLOB,
            file_name_embedding BLOB
        )
        ''')
        
        # Create index for faster retrieval
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_chunks_file_id ON chunks(file_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_chunks_chunk_name ON chunks(chunk_name)')
        
        conn.commit()
        conn.close()
    
    def _process_row(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Process a chunk row into a dictionary with proper types."""
        if not row:
            return None
        
        chunk = dict(row)
        
        # Convert blob to embedding
        if chunk['embedding']:
            chunk['embedding'] = self._blob_to_embedding(chunk['embedding'])
        
        if chunk['file_name_embedding']:
            chunk['file_name_embedding'] = self._blob_to_embedding(chunk['file_name_embedding'])
        
        # Parse tags JSON
        if chunk['tags']:
            chunk['tags'] = json.loads(chunk['tags'])
        else:
            chunk['tags'] = []
        
        return chunk
    
    def add_chunk(self, chunk_name: str, file_id: int, puretext: str, 
                  tags: Optional[List[str]] = None, summary: Optional[str] = None,
                  embedding: Optional[List[float]] = None, 
                  chunk_summary_embedding: Optional[List[float]] = None,
                  ) -> int:
        """Add a chunk to the database.
        
        Args:
            chunk_name: Name of the chunk (e.g., "file1:1")
            file_id: ID of the file this chunk belongs to
            puretext: Raw text content of the chunk
            tags: List of descriptive tags for the chunk
            summary: AI-generated summary of the chunk
            embedding: Semantic embedding vector for the chunk
            file_name_embedding: Embedding of the chunk name
            
        Returns:
            ID of the newly added chunk
        """
        conn = self._connect()
        cursor = conn.cursor()
        
        tags_json = json.dumps(tags) if tags else None
        embedding_blob = self._embedding_to_blob(embedding) if embedding else None
        chunk_summary_embedding = self._embedding_to_blob(chunk_summary_embedding) if chunk_summary_embedding else None
        
        cursor.execute('''
        INSERT INTO chunks (chunk_name, file_id, tags, puretext, summary, embedding, file_name_embedding)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (chunk_name, file_id, tags_json, puretext, summary, embedding_blob, chunk_summary_embedding))
        
        chunk_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return chunk_id
    
    def get_chunk(self, chunk_id: int) -> Dict[str, Any]:
        """Get a chunk by its ID.
        
        Args:
            chunk_id: ID of the chunk to retrieve
            
        Returns:
            Dictionary containing chunk data
        """
        conn = self._connect()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM chunks WHERE id = ?', (chunk_id,))
        row = cursor.fetchone()
        
        conn.close()
        return self._process_row(row)
    
    def chunk_exists(self, chunk_name: str) -> bool:
        """Check if a chunk already exists in the database.
        
        Args:
            chunk_name: Name of the chunk
            
        Returns:
            True if the chunk exists, False otherwise
        """
        conn = self._connect()
        cursor = conn.cursor()
        
        cursor.execute('SELECT id FROM chunks WHERE chunk_name = ?', (chunk_name,))
        result = cursor.fetchone()
        
        conn.close()
        return result is not None
    
    def get_chunks_by_file_id(self, file_id: int) -> List[Dict[str, Any]]:
        """Get all chunks belonging to a file.
        
        Args:
            file_id: ID of the file
            
        Returns:
            List of dictionaries containing chunk data
        """
        conn = self._connect()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM chunks WHERE file_id = ?', (file_id,))
        rows = cursor.fetchall()
        
        chunks = [self._process_row(row) for row in rows]
        
        conn.close()
        return chunks
    
    def update_chunk(self, chunk_id: int, **kwargs) -> bool:
        """Update a chunk in the database.
        
        Args:
            chunk_id: ID of the chunk to update
            **kwargs: Fields to update
            
        Returns:
            True if successful, False otherwise
        """
        conn = self._connect()
        cursor = conn.cursor()
        
        # Prepare SET clause and parameters
        set_clause = []
        params = []
        
        for key, value in kwargs.items():
            if key == 'tags' and value is not None:
                set_clause.append(f"{key} = ?")
                params.append(json.dumps(value))
            elif key == 'embedding' and value is not None:
                set_clause.append(f"{key} = ?")
                params.append(self._embedding_to_blob(value))
            elif key == 'file_name_embedding' and value is not None:
                set_clause.append(f"{key} = ?")
                params.append(self._embedding_to_blob(value))
            elif key in ['chunk_name', 'file_id', 'puretext', 'summary']:
                set_clause.append(f"{key} = ?")
                params.append(value)
        
        if not set_clause:
            conn.close()
            return False
        
        # Add chunk_id to params
        params.append(chunk_id)
        
        # Execute update
        cursor.execute(f'''
        UPDATE chunks
        SET {', '.join(set_clause)}
        WHERE id = ?
        ''', params)
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    def delete_chunk(self, chunk_id: int) -> bool:
        """Delete a chunk from the database.
        
        Args:
            chunk_id: ID of the chunk to delete
            
        Returns:
            True if successful, False otherwise
        """
        conn = self._connect()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM chunks WHERE id = ?', (chunk_id,))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    def search_by_embedding(self, query_embedding: List[float], top_n: int = 5) -> List[Dict[str, Any]]:
        """Search for chunks by embedding similarity.
        
        Args:
            query_embedding: Embedding vector to search for
            top_n: Number of results to return
            
        Returns:
            List of dictionaries containing chunk data and similarity scores
        """
        conn = self._connect()
        cursor = conn.cursor()
        
        # Get all chunks with embeddings
        cursor.execute('SELECT id, chunk_name, file_id, tags, puretext, summary, embedding FROM chunks WHERE embedding IS NOT NULL')
        rows = cursor.fetchall()
        
        # Calculate cosine similarity for each chunk
        results = []
        query_embedding_np = np.array(query_embedding, dtype=np.float32)
        
        for row in rows:
            chunk = self._process_row(row)
            embedding = chunk['embedding']
            
            # Calculate cosine similarity
            embedding_np = np.array(embedding, dtype=np.float32)
            similarity = np.dot(query_embedding_np, embedding_np) / (
                np.linalg.norm(query_embedding_np) * np.linalg.norm(embedding_np)
            )
            
            results.append({
                'chunk': chunk,
                'similarity': float(similarity)
            })
        
        # Sort by similarity (descending)
        results.sort(key=lambda x: x['similarity'], reverse=True)
        
        # Return top N results
        top_results = results[:top_n]
        
        conn.close()
        return top_results


class FileDatabase(BaseDatabase):
    """Database for storing and retrieving file information."""
    
    def __init__(self, db_path: str = "data/files.db"):
        """Initialize the file database.
        
        Args:
            db_path: Path to the SQLite database file
        """
        super().__init__(db_path)
    
    def _get_table_name(self) -> str:
        """Get the table name for this database."""
        return "files"
    
    def _create_tables(self):
        """Create necessary tables if they don't exist."""
        conn = self._connect()
        cursor = conn.cursor()
        
        # Create files table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            tags TEXT,
            puretext TEXT,
            summary TEXT,
            embedding BLOB,
            file_name_embedding BLOB
        )
        ''')
        
        # Create index for faster retrieval
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_files_name ON files(name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_files_file_path ON files(file_path)')
        
        conn.commit()
        conn.close()
    
    def _process_row(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Process a file row into a dictionary with proper types."""
        if not row:
            return None
        
        file = dict(row)
        
        # Convert blob to embedding
        if file['embedding']:
            file['embedding'] = self._blob_to_embedding(file['embedding'])
        
        if file['file_name_embedding']:
            file['file_name_embedding'] = self._blob_to_embedding(file['file_name_embedding'])
        
        # Parse tags JSON
        if file['tags']:
            file['tags'] = json.loads(file['tags'])
        else:
            file['tags'] = []
        
        return file
    
    def add_file(self, name: str, file_path: str, puretext: Optional[str] = None,
                 tags: Optional[List[str]] = None, 
                 file_summary: Optional[str] = None,
                 file_embedding: Optional[List[float]] = None, 
                 file_name_embedding: Optional[List[float]] = None,
                 file_summary_embedding: Optional[List[float]] = None,
                 
                 ) -> int:
        """Add a file to the database.
        
        Args:
            name: Name of the file
            file_path: Path to the file in the system
            puretext: Raw text content of the file
            tags: List of descriptive tags for the file
            summary: AI-generated summary of the file
            embedding: Global embedding for the entire file
            file_name_embedding: Embedding of the file name
            
        Returns:
            ID of the newly added file
        """
        conn = self._connect()
        cursor = conn.cursor()
        
        tags_json = json.dumps(tags) if tags else None
        embedding_blob = self._embedding_to_blob(file_embedding) if file_embedding else None
        file_name_embedding_blob = self._embedding_to_blob(file_name_embedding) if file_name_embedding else None
        
        cursor.execute('''
        INSERT INTO files (name, file_path, tags, puretext, summary, embedding, file_name_embedding)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (name, file_path, tags_json, puretext, file_summary, embedding_blob, file_name_embedding_blob))
        
        file_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return file_id
    
    def file_exists(self, name: str) -> bool:
        """Check if a file already exists in the database.
        
        Args:
            name: Name of the file
            
        Returns:
            True if the file exists, False otherwise
        """
        conn = self._connect()
        cursor = conn.cursor()
        
        cursor.execute('SELECT id FROM files WHERE name = ?', (name,))
        result = cursor.fetchone()
        
        conn.close()
        return result is not None
    
    def get_file_id(self, name: str) -> Optional[int]:
        """Get the ID of a file by its name.
        
        Args:
            name: Name of the file
            
        Returns:
            ID of the file, or None if not found
        """
        conn = self._connect()
        cursor = conn.cursor()
        
        cursor.execute('SELECT id FROM files WHERE name = ?', (name,))
        result = cursor.fetchone()
        
        conn.close()
        return result['id'] if result else None
    
    def get_file(self, file_id: int) -> Dict[str, Any]:
        """Get a file by its ID.
        
        Args:
            file_id: ID of the file to retrieve
            
        Returns:
            Dictionary containing file data
        """
        conn = self._connect()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM files WHERE id = ?', (file_id,))
        row = cursor.fetchone()
        
        conn.close()
        return self._process_row(row)
    
    def get_file_by_name(self, name: str) -> Dict[str, Any]:
        """Get a file by its name.
        
        Args:
            name: Name of the file to retrieve
            
        Returns:
            Dictionary containing file data
        """
        conn = self._connect()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM files WHERE name = ?', (name,))
        row = cursor.fetchone()
        
        conn.close()
        return self._process_row(row)
    
    def get_file_by_path(self, file_path: str) -> Dict[str, Any]:
        """Get a file by its path.
        
        Args:
            file_path: Path of the file to retrieve
            
        Returns:
            Dictionary containing file data
        """
        conn = self._connect()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM files WHERE file_path = ?', (file_path,))
        row = cursor.fetchone()
        
        conn.close()
        return self._process_row(row)
    
    def update_file(self, file_id: int, **kwargs) -> bool:
        """Update a file in the database.
        
        Args:
            file_id: ID of the file to update
            **kwargs: Fields to update
            
        Returns:
            True if successful, False otherwise
        """
        conn = self._connect()
        cursor = conn.cursor()
        
        # Prepare SET clause and parameters
        set_clause = []
        params = []
        
        for key, value in kwargs.items():
            if key == 'tags' and value is not None:
                set_clause.append(f"{key} = ?")
                params.append(json.dumps(value))
            elif key == 'embedding' and value is not None:
                set_clause.append(f"{key} = ?")
                params.append(self._embedding_to_blob(value))
            elif key == 'file_name_embedding' and value is not None:
                set_clause.append(f"{key} = ?")
                params.append(self._embedding_to_blob(value))
            elif key in ['name', 'file_path', 'puretext', 'summary']:
                set_clause.append(f"{key} = ?")
                params.append(value)
        
        if not set_clause:
            conn.close()
            return False
        
        # Add file_id to params
        params.append(file_id)
        
        # Execute update
        cursor.execute(f'''
        UPDATE files
        SET {', '.join(set_clause)}
        WHERE id = ?
        ''', params)
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    def delete_file(self, file_id: int) -> bool:
        """Delete a file from the database.
        
        Args:
            file_id: ID of the file to delete
            
        Returns:
            True if successful, False otherwise
        """
        conn = self._connect()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM files WHERE id = ?', (file_id,))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    def search_by_embedding(self, query_embedding: List[float], top_n: int = 5) -> List[Dict[str, Any]]:
        """Search for files by embedding similarity.
        
        Args:
            query_embedding: Embedding vector to search for
            top_n: Number of results to return
            
        Returns:
            List of dictionaries containing file data and similarity scores
        """
        conn = self._connect()
        cursor = conn.cursor()
        
        # Get all files with embeddings
        cursor.execute('SELECT * FROM files WHERE embedding IS NOT NULL')
        rows = cursor.fetchall()
        
        # Calculate cosine similarity for each file
        results = []
        query_embedding_np = np.array(query_embedding, dtype=np.float32)
        
        for row in rows:
            file = self._process_row(row)
            embedding = file['embedding']
            
            # Calculate cosine similarity
            embedding_np = np.array(embedding, dtype=np.float32)
            similarity = np.dot(query_embedding_np, embedding_np) / (
                np.linalg.norm(query_embedding_np) * np.linalg.norm(embedding_np)
            )
            
            results.append({
                'file': file,
                'similarity': float(similarity)
            })
        
        # Sort by similarity (descending)
        results.sort(key=lambda x: x['similarity'], reverse=True)
        
        # Return top N results
        top_results = results[:top_n]
        
        conn.close()
        return top_results


def count_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
    """Count the number of tokens in a text string.
    
    Args:
        text: The text to count tokens for
        encoding_name: The encoding to use
        
    Returns:
        Number of tokens
    """
    encoding = tiktoken.get_encoding(encoding_name)
    num_tokens = len(encoding.encode(text))
    return num_tokens


def export_table_to_csv(db_path: str, table_name: str, csv_path: str, blacklist: Optional[List[str]] = None):
    """Convert a table from an SQLite database to a CSV file, excluding blacklisted columns.

    Args:
        db_path: Path to the SQLite database file.
        table_name: Name of the table to convert.
        csv_path: Path where the CSV file will be saved.
        blacklist: List of column names to exclude from the CSV.
    """
    blacklist = set(blacklist) if blacklist else set()
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Retrieve column names
    cursor.execute(f'SELECT * FROM {table_name} LIMIT 0')
    column_names = [description[0] for description in cursor.description]

    # Filter out blacklisted columns
    filtered_columns = [name for name in column_names if name not in blacklist]
    
    # Fetch data
    rows = cursor.execute(f'SELECT {", ".join(filtered_columns)} FROM {table_name}').fetchall()
    
    conn.close()

    # Write to CSV
    with open(csv_path, mode='w', newline='', encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(filtered_columns)  # Write headers
        writer.writerows(rows)  # Write data