"""
Search methods for the LORAG system.
"""

import os
import re
import json
import sqlite3
import numpy as np
from typing import List, Dict, Any, Optional, Union, Tuple
from abc import ABC, abstractmethod
from openai import OpenAI
from .database import ChunkDatabase, FileDatabase


class BaseSearchMethod(ABC):
    """Base class for all search methods."""
    
    def __init__(self, chunk_db: ChunkDatabase, file_db: FileDatabase):
        """Initialize the search method.
        
        Args:
            chunk_db: Chunk database instance
            file_db: File database instance
        """
        self.chunk_db = chunk_db
        self.file_db = file_db
    
    @abstractmethod
    def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Search for relevant documents.
        
        Args:
            query: The search query
            **kwargs: Additional search parameters
            
        Returns:
            List of search results
        """
        pass


class EmbeddingSearch(BaseSearchMethod):
    """Standard RAG search using embeddings."""
    
    def __init__(self, chunk_db: ChunkDatabase, file_db: FileDatabase, api_key: str):
        """Initialize the embedding search method.
        
        Args:
            chunk_db: Chunk database instance
            file_db: File database instance
            api_key: OpenAI API key
        """
        super().__init__(chunk_db, file_db)
        self.client = OpenAI(api_key=api_key)
    
    def get_embedding(self, text: str) -> List[float]:
        """Get embedding for a text string.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        response = self.client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
            encoding_format="float"
        )
        return response.data[0].embedding
    
    def search(self, query: str, n_return: int = 5, **kwargs) -> List[Dict[str, Any]]:
        """Search for relevant chunks using embeddings.
        
        Args:
            query: The search query
            n_return: Number of results to return
            **kwargs: Additional search parameters
            
        Returns:
            List of search results
        """
        # Get embedding for the query
        query_embedding = self.get_embedding(query)
        
        # Search for chunks by embedding similarity
        results = self.chunk_db.search_by_embedding(query_embedding, top_n=n_return)
        
        # Format results
        formatted_results = []
        for result in results:
            chunk = result['chunk']
            file = self.file_db.get_file(chunk['file_id'])
            
            formatted_results.append({
                'chunk_id': chunk['id'],
                'chunk_name': chunk['chunk_name'],
                'file_id': file['id'],
                'file_name': file['name'],
                'file_path': file['file_path'],
                'content': chunk['puretext'],
                'summary': chunk['summary'],
                'similarity': result['similarity'],
                'method': 'embedding'
            })
        
        return formatted_results


class FileNameLookup(BaseSearchMethod):
    """Search by file name."""
    
    def search(self, query: str, n_return: int = 5, **kwargs) -> List[Dict[str, Any]]:
        """Search for files by name.
        
        Args:
            query: The search query (file name or pattern)
            n_return: Number of results to return
            **kwargs: Additional search parameters
            
        Returns:
            List of search results
        """
        conn = self.file_db._connect()
        cursor = conn.cursor()
        
        # Search for files with names containing the query
        cursor.execute('''
        SELECT * FROM files
        WHERE name LIKE ?
        LIMIT ?
        ''', (f'%{query}%', n_return))
        
        rows = cursor.fetchall()
        
        # Format results
        results = []
        for row in rows:
            file = dict(row)
            
            # Parse tags JSON
            if file['tags']:
                file['tags'] = json.loads(file['tags'])
            else:
                file['tags'] = []
            
            # Get first chunk for preview
            cursor.execute('SELECT * FROM chunks WHERE file_id = ? LIMIT 1', (file['id'],))
            chunk_row = cursor.fetchone()
            chunk = dict(chunk_row) if chunk_row else None
            
            results.append({
                'file_id': file['id'],
                'file_name': file['name'],
                'file_path': file['file_path'],
                'content': chunk['puretext'] if chunk else None,
                'summary': file['summary'],
                'similarity': 1.0,  # Direct match has highest similarity
                'method': 'file_name_lookup'
            })
        
        conn.close()
        return results


class FileNameEmbeddingSearch(BaseSearchMethod):
    """Give a llm current context and list of all files, and ask it to rank the most relevant file name.
    """
    
    def __init__(self, chunk_db: ChunkDatabase, file_db: FileDatabase, api_key: str, messages: Optional[List[Dict[str, str]]] = None):
        """Initialize the file name RAG search method.
        
        Args:
            chunk_db: Chunk database instance
            file_db: File database instance
            api_key: OpenAI API key
            messages: List of messages to provide context, in format of OpenAI
        """
        super().__init__(chunk_db, file_db)
        self.client = OpenAI(api_key=api_key)
        self.messages = messages if messages else []
    
    def get_embedding(self, text: str) -> List[float]:
        """Get embedding for a text string.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        response = self.client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
            encoding_format="float"
        )
        return response.data[0].embedding
    
    def search(self, query: str, n_return: int = 5, **kwargs) -> List[Dict[str, Any]]:
        """Search for files by name embedding similarity.
        
        Args:
            query: The search query
            n_return: Number of results to return
            **kwargs: Additional search parameters
            
        Returns:
            List of search results
        """
        # Get embedding for the query
        query_embedding = self.get_embedding(query)
        
        conn = self.file_db._connect()
        cursor = conn.cursor()
        
        # Get all files with file_name_embedding embeddings
        cursor.execute('SELECT * FROM files WHERE file_name_embedding IS NOT NULL')
        rows = cursor.fetchall()
        
        # Calculate cosine similarity for each file
        results = []
        query_embedding_np = np.array(query_embedding, dtype=np.float32)
        
        for row in rows:
            file = dict(row)
            file_name_embedding = self.file_db._blob_to_embedding(file['file_name_embedding'])
            
            # Calculate cosine similarity
            embedding_np = np.array(file_name_embedding, dtype=np.float32)
            similarity = np.dot(query_embedding_np, embedding_np) / (
                np.linalg.norm(query_embedding_np) * np.linalg.norm(embedding_np)
            )
            
            # Parse tags JSON
            if file['tags']:
                file['tags'] = json.loads(file['tags'])
            else:
                file['tags'] = []
            
            # Get first chunk for preview
            cursor.execute('SELECT * FROM chunks WHERE file_id = ? LIMIT 1', (file['id'],))
            chunk_row = cursor.fetchone()
            chunk = dict(chunk_row) if chunk_row else None
            
            results.append({
                'file': file,
                'content': chunk['puretext'] if chunk else None,
                'similarity': float(similarity),
                'method': 'file_name_embedding'
            })
        
        # Sort by similarity (descending)
        results.sort(key=lambda x: x['similarity'], reverse=True)
        
        # Return top N results
        top_results = results[:n_return]
        
        # Format results
        formatted_results = []
        for result in top_results:
            file = result['file']
            
            formatted_results.append({
                'file_id': file['id'],
                'file_name': file['name'],
                'file_path': file['file_path'],
                'content': result['content'],
                'summary': file['summary'],
                'similarity': result['similarity'],
                'method': 'file_name_embedding'
            })
        
        conn.close()
        return formatted_results


class SummaryRAGChunk(BaseSearchMethod):
    """Search using summaries of chunks."""
    
    def __init__(self, chunk_db: ChunkDatabase, file_db: FileDatabase, api_key: str):
        """Initialize the summary RAG chunk search method.
        
        Args:
            chunk_db: Chunk database instance
            file_db: File database instance
            api_key: OpenAI API key
        """
        super().__init__(chunk_db, file_db)
        self.client = OpenAI(api_key=api_key)
    
    def get_embedding(self, text: str) -> List[float]:
        """Get embedding for a text string.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        response = self.client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
            encoding_format="float"
        )
        return response.data[0].embedding
    
    def search(self, query: str, n_return: int = 5, **kwargs) -> List[Dict[str, Any]]:
        """Search for chunks by summary embedding similarity.
        
        Args:
            query: The search query
            n_return: Number of results to return
            **kwargs: Additional search parameters
            
        Returns:
            List of search results
        """
        # Get embedding for the query
        query_embedding = self.get_embedding(query)
        
        conn = self.chunk_db._connect()
        cursor = conn.cursor()
        
        # Get all chunks with summaries
        cursor.execute('SELECT * FROM chunks WHERE summary IS NOT NULL')
        rows = cursor.fetchall()
        
        # Calculate cosine similarity for each chunk's summary
        results = []
        query_embedding_np = np.array(query_embedding, dtype=np.float32)
        
        for row in rows:
            chunk = dict(row)
            
            # Get embedding for the summary
            summary_embedding = self.get_embedding(chunk['summary'])
            
            # Calculate cosine similarity
            embedding_np = np.array(summary_embedding, dtype=np.float32)
            similarity = np.dot(query_embedding_np, embedding_np) / (
                np.linalg.norm(query_embedding_np) * np.linalg.norm(embedding_np)
            )
            
            # Parse tags JSON
            if chunk['tags']:
                chunk['tags'] = json.loads(chunk['tags'])
            else:
                chunk['tags'] = []
            
            results.append({
                'chunk': chunk,
                'similarity': float(similarity)
            })
        
        # Sort by similarity (descending)
        results.sort(key=lambda x: x['similarity'], reverse=True)
        
        # Return top N results
        top_results = results[:n_return]
        
        # Format results
        formatted_results = []
        for result in top_results:
            chunk = result['chunk']
            file = self.file_db.get_file(chunk['file_id'])
            
            formatted_results.append({
                'chunk_id': chunk['id'],
                'chunk_name': chunk['chunk_name'],
                'file_id': file['id'],
                'file_name': file['name'],
                'file_path': file['file_path'],
                'content': chunk['puretext'],
                'summary': chunk['summary'],
                'similarity': result['similarity'],
                'method': 'summary_rag_chunk'
            })
        
        conn.close()
        return formatted_results


class SummaryRAGDocument(BaseSearchMethod):
    """Search using summaries of entire documents."""
    
    def __init__(self, chunk_db: ChunkDatabase, file_db: FileDatabase, api_key: str):
        """Initialize the summary RAG document search method.
        
        Args:
            chunk_db: Chunk database instance
            file_db: File database instance
            api_key: OpenAI API key
        """
        super().__init__(chunk_db, file_db)
        self.client = OpenAI(api_key=api_key)
    
    def get_embedding(self, text: str) -> List[float]:
        """Get embedding for a text string.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        response = self.client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
            encoding_format="float"
        )
        return response.data[0].embedding
    
    def search(self, query: str, n_return: int = 5, **kwargs) -> List[Dict[str, Any]]:
        """Search for files by summary embedding similarity.
        
        Args:
            query: The search query
            n_return: Number of results to return
            **kwargs: Additional search parameters
            
        Returns:
            List of search results
        """
        # Get embedding for the query
        query_embedding = self.get_embedding(query)
        
        conn = self.file_db._connect()
        cursor = conn.cursor()
        
        # Get all files with summaries
        cursor.execute('SELECT * FROM files WHERE summary IS NOT NULL')
        rows = cursor.fetchall()
        
        # Calculate cosine similarity for each file's summary
        results = []
        query_embedding_np = np.array(query_embedding, dtype=np.float32)
        
        for row in rows:
            file = dict(row)
            
            # Get embedding for the summary
            summary_embedding = self.get_embedding(file['summary'])
            
            # Calculate cosine similarity
            embedding_np = np.array(summary_embedding, dtype=np.float32)
            similarity = np.dot(query_embedding_np, embedding_np) / (
                np.linalg.norm(query_embedding_np) * np.linalg.norm(embedding_np)
            )
            
            # Parse tags JSON
            if file['tags']:
                file['tags'] = json.loads(file['tags'])
            else:
                file['tags'] = []
            
            # Get first chunk for preview
            cursor.execute('SELECT * FROM chunks WHERE file_id = ? LIMIT 1', (file['id'],))
            chunk_row = cursor.fetchone()
            chunk = dict(chunk_row) if chunk_row else None
            
            results.append({
                'file': file,
                'content': chunk['puretext'] if chunk else None,
                'similarity': float(similarity)
            })
        
        # Sort by similarity (descending)
        results.sort(key=lambda x: x['similarity'], reverse=True)
        
        # Return top N results
        top_results = results[:n_return]
        
        # Format results
        formatted_results = []
        for result in top_results:
            file = result['file']
            
            formatted_results.append({
                'file_id': file['id'],
                'file_name': file['name'],
                'file_path': file['file_path'],
                'content': result['content'],
                'summary': file['summary'],
                'similarity': result['similarity'],
                'method': 'summary_rag_document'
            })
        
        conn.close()
        return formatted_results


class RegexSearch(BaseSearchMethod):
    """Search using regular expressions."""
    
    def search(self, query: str, n_return: int = 5, **kwargs) -> List[Dict[str, Any]]:
        """Search for chunks using regex pattern.
        
        Args:
            query: The regex pattern to search for
            n_return: Number of results to return
            **kwargs: Additional search parameters
            
        Returns:
            List of search results
        """
        conn = self.chunk_db._connect()
        cursor = conn.cursor()
        
        # Get all chunks
        cursor.execute('SELECT * FROM chunks')
        rows = cursor.fetchall()
        
        # Search for pattern in each chunk
        results = []
        pattern = re.compile(query, re.IGNORECASE)
        
        for row in rows:
            chunk = dict(row)
            
            # Search for pattern in chunk text
            matches = pattern.findall(chunk['puretext'])
            
            if matches:
                # Parse tags JSON
                if chunk['tags']:
                    chunk['tags'] = json.loads(chunk['tags'])
                else:
                    chunk['tags'] = []
                
                file = self.file_db.get_file(chunk['file_id'])
                
                results.append({
                    'chunk_id': chunk['id'],
                    'chunk_name': chunk['chunk_name'],
                    'file_id': file['id'],
                    'file_name': file['name'],
                    'file_path': file['file_path'],
                    'content': chunk['puretext'],
                    'summary': chunk['summary'],
                    'matches': len(matches),
                    'method': 'regex'
                })
        
        # Sort by number of matches (descending)
        results.sort(key=lambda x: x['matches'], reverse=True)
        
        # Return top N results
        top_results = results[:n_return]
        
        # Format results
        formatted_results = []
        for result in top_results:
            # Calculate a similarity score based on number of matches
            max_matches = max([r['matches'] for r in results]) if results else 1
            similarity = result['matches'] / max_matches if max_matches > 0 else 0
            
            formatted_result = {
                'chunk_id': result['chunk_id'],
                'chunk_name': result['chunk_name'],
                'file_id': result['file_id'],
                'file_name': result['file_name'],
                'file_path': result['file_path'],
                'content': result['content'],
                'summary': result['summary'],
                'similarity': similarity,
                'method': 'regex'
            }
            
            formatted_results.append(formatted_result)
        
        conn.close()
        return formatted_results


class FileStructureTraversal(BaseSearchMethod):
    """Search by traversing file structure."""
    
    def search(self, query: str, n_return: int = 5, **kwargs) -> List[Dict[str, Any]]:
        """Search for files by traversing file structure.
        
        Args:
            query: The search query (directory path or pattern)
            n_return: Number of results to return
            **kwargs: Additional search parameters
            
        Returns:
            List of search results
        """
        conn = self.file_db._connect()
        cursor = conn.cursor()
        
        # Search for files in the specified directory
        cursor.execute('''
        SELECT * FROM files
        WHERE file_path LIKE ?
        LIMIT ?
        ''', (f'{query}%', n_return))
        
        rows = cursor.fetchall()
        
        # Format results
        results = []
        for row in rows:
            file = dict(row)
            
            # Parse tags JSON
            if file['tags']:
                file['tags'] = json.loads(file['tags'])
            else:
                file['tags'] = []
            
            # Get first chunk for preview
            cursor.execute('SELECT * FROM chunks WHERE file_id = ? LIMIT 1', (file['id'],))
            chunk_row = cursor.fetchone()
            chunk = dict(chunk_row) if chunk_row else None
            
            results.append({
                'file_id': file['id'],
                'file_name': file['name'],
                'file_path': file['file_path'],
                'content': chunk['puretext'] if chunk else None,
                'summary': file['summary'],
                'similarity': 1.0,  # Direct match has highest similarity
                'method': 'file_structure'
            })
        
        conn.close()
        return results


class SQLQuery(BaseSearchMethod):
    """Search using SQL queries."""
    
    def search(self, query: str, n_return: int = 5, **kwargs) -> List[Dict[str, Any]]:
        """Search using custom SQL query.
        
        Args:
            query: The SQL query to execute
            n_return: Number of results to return
            **kwargs: Additional search parameters
            
        Returns:
            List of search results
        """
        conn = self.chunk_db._connect()
        cursor = conn.cursor()
        
        # Execute the SQL query
        try:
            cursor.execute(query)
            rows = cursor.fetchall()
        except sqlite3.Error as e:
            conn.close()
            return [{'error': str(e), 'method': 'sql_query'}]
        
        # Format results
        results = []
        for row in rows:
            result = dict(row)
            
            # Add method information
            result['method'] = 'sql_query'
            
            results.append(result)
        
        # Limit results
        limited_results = results[:n_return]
        
        conn.close()
        return limited_results


class QueryRewriting(BaseSearchMethod):
    """Rewrite queries to improve searchability."""
    
    def __init__(self, chunk_db: ChunkDatabase, file_db: FileDatabase, api_key: str):
        """Initialize the query rewriting search method.
        
        Args:
            chunk_db: Chunk database instance
            file_db: File database instance
            api_key: OpenAI API key
        """
        super().__init__(chunk_db, file_db)
        self.client = OpenAI(api_key=api_key)
    
    def rewrite_query(self, query: str) -> str:
        """Rewrite a query to improve searchability.
        
        Args:
            query: The original query
            
        Returns:
            Rewritten query
        """
        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that rewrites search queries to improve their searchability. Convert questions into statements, expand acronyms, and add relevant keywords."},
                {"role": "user", "content": f"Rewrite this search query to improve its searchability: {query}"}
            ]
        )
        
        return response.choices[0].message.content
    
    def search(self, query: str, n_return: int = 5, search_method: BaseSearchMethod = None, **kwargs) -> List[Dict[str, Any]]:
        """Rewrite query and search using another method.
        
        Args:
            query: The search query
            n_return: Number of results to return
            search_method: The search method to use with the rewritten query
            **kwargs: Additional search parameters
            
        Returns:
            List of search results
        """
        if search_method is None:
            return [{'error': 'No search method provided', 'method': 'query_rewriting'}]
        
        # Rewrite the query
        rewritten_query = self.rewrite_query(query)
        
        # Search using the provided method
        results = search_method.search(rewritten_query, n_return=n_return, **kwargs)
        
        # Add rewritten query information
        for result in results:
            result['original_query'] = query
            result['rewritten_query'] = rewritten_query
            result['method'] = f"query_rewriting+{result['method']}"
        
        return results