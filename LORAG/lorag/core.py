"""
Core module for the LORAG system.
"""

import os
from typing import List, Dict, Any, Optional

from lorag.database import ChunkDatabase, FileDatabase
from lorag.embedding_manager import EmbeddingManager
from lorag.text_processing import TextProcessor
from lorag.document_search_engine import DocumentSearchEngine
from lorag.batch import BatchProcessor
from lorag.logger import logger
from dataclasses import dataclass, field

@dataclass
class LORAGFeature:
    """Configuration for LORAG system feature."""
    
    chunk_embedding: bool = True
    file_name_embedding: bool = True
    summary: bool = True
    summary_embedding: bool = True
    document_embedding: bool = True
    sql_querying: bool = True
    
class LORAG:
    """LORAG (Layered or Hybrid RAG) system."""
    
    def __init__(self, 
            api_key: str, 
            chunk_db_path: str = "data/bright/index/chunks.db", 
            file_db_path: str = "data/bright/index/files.db",
            lm_model = "gpt-4o",
            embedding_model = "text-embedding-3-small",
            feature=LORAGFeature(),
            verbose: bool = False
            ):
        """Initialize the LORAG system.
        
        Args:
            api_key: OpenAI API key
            chunk_db_path: Path to the chunk database
            file_db_path: Path to the file database
            lm_model: Language model to use
            embedding_model: Embedding model to use (support any OpenAI model, or give local path to use)
        """
        self.api_key = api_key
        self.lm_model = lm_model
        self.verbose = verbose
        # detect if is local model (contain dot)
        if "." in embedding_model:
            # local model
            self.local_model = True
        else:
            # remote model
            self.local_model = False
            
        self.embedding_model = embedding_model
        self.feature = feature
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(chunk_db_path), exist_ok=True)
        os.makedirs(os.path.dirname(file_db_path), exist_ok=True)
        
        # Initialize databases
        self.chunk_db = ChunkDatabase(chunk_db_path)
        self.file_db = FileDatabase(file_db_path)
        
        # Initialize components
        self.embedding_manager = EmbeddingManager(api_key)
        self.text_processor = TextProcessor(api_key)
        self.document_search_engine = DocumentSearchEngine(api_key, self.chunk_db, self.file_db, self.text_processor)
        self.batch_processor = BatchProcessor(api_key, chunk_db_path, file_db_path)
    
    def add_file(self, file_path: str, chunk_size: int = 1000, chunk_overlap: int = 200, 
                force_update: bool = False) -> Dict[str, Any]:
        """Add a file to the system.
        
        Args:
            file_path: Path to the file
            chunk_size: Size of each chunk (in characters)
            chunk_overlap: Overlap between chunks (in characters)
            force_update: If True, update the file even if it already exists
            
        Returns:
            Dictionary with file ID and status information:
            {
                "file_id": ID of the added file,
                "status": "added" | "existing" | "updated",
                "file_name": Name of the file
            }
        """
        return self.add_files([file_path], chunk_size, chunk_overlap, force_update)
    
    def add_files(self, file_paths: List[str], chunk_size: int = 1000,
                chunk_overlap: int = 200, force_update: bool = False) -> Dict[str, Any]:
        """Add multiple files to the system.
        
        Args:
            file_paths: List of file paths
            chunk_size: Size of each chunk (in characters)
            chunk_overlap: Overlap between chunks (in characters)
            force_update: If True, update the file even if it already exists
            
        Returns:
            Dictionary with file IDs and status information:
            {
                "file_ids": List of IDs of the added files,
                "status": "added" | "existing" | "updated",
                "file_names": List of names of the files
            }
        """
        
        for file_path in file_paths:
            if not os.path.isfile(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            
        texts = []
        for file_path in file_paths:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            file_name = os.path.basename(file_path)
            texts.append((content, file_name))
            
        names = []
        for file_path in file_paths:
            names.append(os.path.basename(file_path))
        return self.add_texts(texts, names, chunk_size, chunk_overlap, force_update)
    
    def add_text(self, text: str, name: str, file_path: Optional[str] = None,
                chunk_size: int = 1000, chunk_overlap: int = 200, force_update: bool = False) -> Dict[str, Any]:
        """Add text directly to the system. You should not call this if there is more than one text
        
        Args:
            text: Text content
            name: Name for the text
            file_path: Path to the file (optional)
            chunk_size: Size of each chunk (in tokens)
            chunk_overlap: Overlap between chunks (in tokens)
            force_update: If True, update the file even if it already exists
            
        Returns:
            Dictionary with file ID and status information:
            {
                "file_id": ID of the added file,
                "status": "added" | "existing" | "updated",
                "file_name": Name of the file,
                "chunks": {
                    "total": Total number of chunks,
                    "added": Number of newly added chunks,
                    "existing": Number of existing chunks
                }
            }
        """
        return self.add_text(text, name, file_path, chunk_size, chunk_overlap, force_update)
    
    def add_texts(self, texts:list, names:list, file_paths:list = None, 
                chunk_size: int = 1000, chunk_overlap: int = 200, force_update: bool = False) -> Dict[str, Any]:
        
        # throw and error if there are more than one text with same name
        if len(set(names)) != len(names):
            raise ValueError("There are duplicate names in the texts")
        
        # Set default file path if not provided
        for i, name in enumerate(names):
            if file_paths[i] is None:
                file_paths[i] = f"memory/{name}"
        for i, name in enumerate(names):
            # Check if file already exists
            existing_file = None
            try:
                existing_file = self.file_db.get_file_by_name(name)
                
                if not force_update and existing_file:
                    print(f"File '{name}' already exists with ID: {existing_file['id']}")
                    return {
                        "file_id": existing_file['id'],
                        "status": "existing",
                        "file_name": name,
                        "chunks": {
                            "total": 0,
                            "added": 0,
                            "existing": 0
                        }
                    }
            except Exception:
                # File doesn't exist, continue with adding
                pass
        process_infos = []
        for i, (text, name, file_path) in enumerate(zip(texts, names, file_paths)):
        
            # Generate file summary
            file_summary = self.text_processor.generate_summary(text)
            # Get file embedding
            file_embedding = self.embedding_manager.get_embedding(text)
            file_summary_embedding = self.embedding_manager.get_embedding(file_summary)
            # Get file name embedding
            file_name_embedding = self.embedding_manager.get_embedding(name)
            
            # Add or update file in database
            if existing_file and force_update:
                # Update existing file
                self.file_db.update_file(
                    existing_file['id'],
                    puretext=text,
                    file_summary=file_summary,
                    file_embedding=file_embedding,
                    file_name_embedding=file_name_embedding,
                    file_summary_embedding=file_summary_embedding
                )
                file_id = existing_file['id']
                status = "updated"
                if self.verbose:
                    print(f"Updated file '{name}' (ID: {file_id})")
            else:
                # Add new file
                file_id = self.file_db.add_file(
                    name=name,
                    file_path=file_path,
                    puretext=text,
                    file_summary=file_summary,
                    file_embedding=file_embedding,
                    file_name_embedding=file_name_embedding,
                    file_summary_embedding=file_summary_embedding
                )
                status = "added"
                if self.verbose:
                    print(f"Added new file '{name}' (ID: {file_id})")
            
            # Chunk the text
            chunks = self.text_processor.chunk_text_token(text, chunk_size, chunk_overlap)
            
            # Track chunk statistics
            chunk_stats = {
                "total": len(chunks),
                "added": 0,
                "existing": 0
            }
            
            # Add chunks to database
            for i, chunk_text in enumerate(chunks):
                chunk_name = f"{name}:{i}"
                
                # Check if chunk already exists
                if self.chunk_db.chunk_exists(chunk_name):
                    chunk_stats["existing"] += 1
                    print(f"Chunk '{chunk_name}' already exists, skipping")
                    continue
                
                # Generate chunk summary
                chunk_summary = self.text_processor.generate_summary(chunk_text)
                
                # Get chunk embedding
                chunk_embedding = self.embedding_manager.get_embedding(chunk_text)
                
                chunk_summary_embedding = self.embedding_manager.get_embedding(chunk_summary)
                
                # Add chunk to database
                self.chunk_db.add_chunk(
                    chunk_name=chunk_name,
                    file_id=file_id,
                    puretext=chunk_text,
                    summary=chunk_summary,
                    embedding=chunk_embedding,
                    chunk_summary_embedding=chunk_summary_embedding
                )
                
                chunk_stats["added"] += 1
            
            process_infos.append({
                "file_id": file_id,
                "status": status,
                "file_name": name,
                "chunks": chunk_stats
            })
        
        # Return process information
        return process_infos
    
    def add_texts_batch(self, texts: List[Dict[str, str]], chunk_size: int = 1000, 
                       chunk_overlap: int = 200, batch_size: int = 100) -> Dict[str, Any]:
        """Add multiple texts to the system in batches.
        
        Args:
            texts: List of dictionaries with 'name' and 'content' keys
            chunk_size: Size of each chunk (in characters)
            chunk_overlap: Overlap between chunks (in characters)
            batch_size: Number of texts to process in each batch
            
        Returns:
            Dictionary with file IDs and statistics:
            {
                "file_ids": List of file IDs,
                "stats": {
                    "total": Total number of texts,
                    "new_embedded": Number of newly embedded texts,
                    "new_summarized": Number of newly summarized texts,
                    "existing": Number of existing texts,
                    "skipped": Number of skipped texts
                }
            }
        """
        return self.batch_processor.add_texts_batch(texts, chunk_size, chunk_overlap, batch_size)
    
    def search(self, query: str, search_mode: str = "all", n_return: int = 5, 
               n_token: Optional[int] = None, n_confidence: Optional[int] = None,
               blacklist_file: Optional[List[str]] = None, effort: int = 1,
               weights: Optional[Dict[str, float]] = None, **kwargs) -> Dict[str, Any]:
        """Search for relevant documents.
        
        Args:
            query: The search query
            search_mode: Search mode ("all", "raw", "smart", or "order")
            n_return: Number of results to return
            n_token: Maximum token count for results
            n_confidence: Number of top files to consider for confidence scoring
            blacklist_file: List of files to ignore
            effort: Computational budget or depth of search
            weights: Weights for each search method
            **kwargs: Additional search parameters
            
        Returns:
            Search results
        """
        return self.document_search_engine.search(
            query=query,
            search_mode=search_mode,
            n_return=n_return,
            n_token=n_token,
            n_confidence=n_confidence,
            blacklist_file=blacklist_file,
            effort=effort,
            weights=weights,
            **kwargs
        )