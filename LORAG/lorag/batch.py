
"""
Batch processing module for LORAG.

This module provides functionality for batch processing of documents,
including embedding and summarization.
"""

import os
import json
import time
from typing import List, Dict, Any, Optional, Union, Tuple
import tiktoken
from tqdm import tqdm
from openai import OpenAI


from lorag.embedding_manager import EmbeddingManager

from .database import ChunkDatabase, FileDatabase, count_tokens
from lorag.logger import logger

class BatchProcessor:
    """Batch processor for LORAG."""
    
    def __init__(self, api_key: str, 
                 chunk_db_path: str = "data/bright/index/chunks.db", 
                 file_db_path: str = "data/bright/index/files.db"):
        """
        Initialize the batch processor.
        
        Args:
            api_key: OpenAI API key
            chunk_db_path: Path to the chunk database
            file_db_path: Path to the file database
        """
        self.api_key = api_key
        # Keep self.client around for summary generation
        self.client = OpenAI(api_key=api_key)
        # Use the EmbeddingManager for embeddings
        self.embedding_manager = EmbeddingManager(api_key)
        
        # Initialize databases
        self.chunk_db = ChunkDatabase(chunk_db_path)
        self.file_db = FileDatabase(file_db_path)
    
    
    
    def prepare_batch_embeddings(
        self, 
        texts: List[Dict[str, str]],
        output_file: str = "data/batch_embeddings.jsonl"
    ) -> str:
        """
        Prepare a batch JSONL file for embedding texts using EmbeddingManager.

        Args:
            texts: List of dictionaries with 'name' and 'content' keys.
            output_file: Path to the output JSONL file.

        Returns:
            Path to the prepared batch file.
        """
        batch_requests = []
        
        for i, text_item in enumerate(texts):
            name = text_item.get('name', f"text_{i}")
            content = text_item.get('content', '')
            
            # Skip if already embedded
            if self.file_db.file_exists(name):
                logger.info(f"Skipping already embedded file: {name}")
                continue
            
            # We'll simply store custom_id & truncated content
            batch_request = {
                "custom_id": name,
                "content": content[:8000]  # limit to first 8000 chars for embedding
            }
            batch_requests.append(batch_request)
        
        # Write out the batch file as JSONL
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w') as f:
            for request in batch_requests:
                f.write(json.dumps(request) + '\n')
        
        logger.info(
            f"Prepared batch embeddings file with {len(batch_requests)} requests: {output_file}"
        )
        return output_file
    
    def prepare_batch_summaries(
        self, 
        texts: List[Dict[str, str]], 
        output_file: str = "data/batch_summaries.jsonl"
    ) -> str:
        """
        Prepare a batch JSONL file for summarizing texts.

        Args:
            texts: List of dictionaries with 'name' and 'content' keys.
            output_file: Path to the output JSONL file.

        Returns:
            Path to the prepared batch file.
        """
        batch_requests = []
        
        for i, text_item in enumerate(texts):
            name = text_item.get('name', f"text_{i}")
            content = text_item.get('content', '')
            
            batch_request = {
                "custom_id": name,
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {
                            "role": "system", 
                            "content": "You are a helpful assistant that summarizes text."
                        },
                        {
                            "role": "user", 
                            "content": f"Please summarize the following text in a concise paragraph:\n\n{content[:4000]}"
                        }
                    ],
                    "max_tokens": 300
                }
            }
            batch_requests.append(batch_request)
        
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w') as f:
            for request in batch_requests:
                f.write(json.dumps(request) + '\n')
        
        logger.info(
            f"Prepared batch summaries file with {len(batch_requests)} requests: {output_file}"
        )
        return output_file
    
    def process_batch_embeddings(
        self, 
        batch_file: str,
        output_file: str = "data/batch_embeddings_results.jsonl"
    ) -> Dict[str, Any]:
        """
        Process a batch of embedding requests using EmbeddingManager's get_embedding_batch.

        Args:
            batch_file: Path to the input JSONL file (created by prepare_batch_embeddings).
            output_file: Path to write the resulting embeddings JSONL.

        Returns:
            Dictionary with basic statistics about the batch (total, success, error).
        """
        # Read batch file
        with open(batch_file, 'r') as f:
            batch_requests = [json.loads(line) for line in f]
        
        # Gather texts and custom IDs
        custom_ids = []
        contents = []
        for req in batch_requests:
            custom_id = req["custom_id"]
            text = req["content"]
            custom_ids.append(custom_id)
            contents.append(text)
        
        # Use embedding manager to fetch all embeddings at once
        stats = {
            "total": len(batch_requests),
            "success": 0,
            "error": 0
        }
        results = []
        
        if not contents:
            logger.info("No new texts to embed.")
            return stats
        
        # Attempt batch embeddings
        try:
            batch_embeddings = self.embedding_manager.get_embedding_batch(
                contents, 
                model="text-embedding-3-small"
            )
        except Exception as e:
            logger.error(f"Error in get_embedding_batch: {str(e)}")
            # If something fails at the batch level, mark them all as errors.
            stats["error"] = stats["total"]
            return stats
        
        # Map each custom_id to the returned embedding
        for i, custom_id in enumerate(custom_ids):
            # The keys in get_embedding_batch are "request-1", "request-2", ...
            key = f"request-{i+1}"
            if key in batch_embeddings:
                embedding = batch_embeddings[key]
                results.append({"custom_id": custom_id, "embedding": embedding})
                stats["success"] += 1
            else:
                logger.warning(f"No embedding found for key {key} (custom_id: {custom_id})")
                stats["error"] += 1
        
        # Write out results to file
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w') as f:
            for result in results:
                f.write(json.dumps(result) + '\n')
        
        logger.info(f"Processed {stats['success']} embeddings with {stats['error']} errors.")
        return stats
    
    def process_batch_summaries(
        self, 
        batch_file: str, 
        output_file: str = "data/batch_summaries_results.jsonl"
    ) -> Dict[str, Any]:
        """
        Process a batch of summaries using the OpenAI API (chat completions).

        Args:
            batch_file: Path to the batch file.
            output_file: Path to the output file.

        Returns:
            Dictionary with statistics.
        """
        with open(batch_file, 'r') as f:
            batch_requests = [json.loads(line) for line in f]
        
        results = []
        stats = {
            "total": len(batch_requests),
            "success": 0,
            "error": 0
        }
        
        for request in tqdm(batch_requests, desc="Processing summaries"):
            try:
                custom_id = request.get('custom_id')
                body = request.get('body', {})
                
                # Summaries use chat completions
                response = self.client.chat.completions.create(
                    model=body.get('model', 'gpt-3.5-turbo'),
                    messages=body.get('messages', []),
                    max_tokens=body.get('max_tokens', 300)
                )
                
                summary = response.choices[0].message.content
                results.append({"custom_id": custom_id, "summary": summary})
                stats["success"] += 1
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"Error processing summary for {request.get('custom_id')}: {str(e)}")
                stats["error"] += 1
        
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w') as f:
            for result in results:
                f.write(json.dumps(result) + '\n')
        
        logger.info(f"Processed {stats['success']} summaries with {stats['error']} errors.")
        return stats
    
    def add_texts_batch(
        self, 
        texts: List[Dict[str, str]], 
        chunk_size: int = 1000,
        chunk_overlap: int = 200, 
        batch_size: int = 100
    ) -> Dict[str, Any]:
        """
        Add multiple texts to the system in batches.

        Args:
            texts: List of dictionaries with 'name' and 'content' keys.
            chunk_size: Size of each chunk (in tokens or chars depending on policy).
            chunk_overlap: Overlap between chunks.
            batch_size: Number of texts to process in each batch.

        Returns:
            Dictionary with file IDs and stats.
        """
        stats = {
            "total": len(texts),
            "new_embedded": 0,
            "new_summarized": 0,
            "existing": 0,
            "skipped": 0
        }
        file_ids = []
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i+batch_size]
            
            # Prepare batch embeddings
            embeddings_file = self.prepare_batch_embeddings(batch_texts)
            # Process batch embeddings
            embeddings_stats = self.process_batch_embeddings(embeddings_file)
            stats["new_embedded"] += embeddings_stats["success"]
            
            # Prepare batch summaries
            summaries_file = self.prepare_batch_summaries(batch_texts)
            # Process batch summaries
            summaries_stats = self.process_batch_summaries(summaries_file)
            stats["new_summarized"] += summaries_stats["success"]
            
            # Load embeddings results
            embeddings_results = {}
            if os.path.exists("data/batch_embeddings_results.jsonl"):
                with open("data/batch_embeddings_results.jsonl", 'r') as f:
                    for line in f:
                        result = json.loads(line)
                        embeddings_results[result["custom_id"]] = result["embedding"]
            
            # Load summaries results
            summaries_results = {}
            if os.path.exists("data/batch_summaries_results.jsonl"):
                with open("data/batch_summaries_results.jsonl", 'r') as f:
                    for line in f:
                        result = json.loads(line)
                        summaries_results[result["custom_id"]] = result["summary"]
            
            # Add texts to database
            for text_item in batch_texts:
                name = text_item.get('name')
                content = text_item.get('content', '')
                
                # Skip if already exists
                if self.file_db.file_exists(name):
                    stats["existing"] += 1
                    file_id = self.file_db.get_file_id(name)
                    if file_id:
                        file_ids.append(file_id)
                    continue
                
                # Get embedding and summary for the file
                embedding = embeddings_results.get(name)
                summary = summaries_results.get(name)
                
                if not embedding or not summary:
                    stats["skipped"] += 1
                    continue
                
                # Add file to database
                file_id = self.file_db.add_file(
                    name=name,
                    file_path=f"memory/{name}",
                    puretext=content,
                    summary=summary,
                    embedding=embedding,
                    file_name_embedding=self.get_embedding(name)  # uses new get_embedding
                )
                file_ids.append(file_id)
                
                # Chunk the text
                chunks = self._chunk_text_token(content, chunk_size, chunk_overlap)
                
                # Add chunks to database
                for idx, chunk_text in enumerate(chunks):
                    chunk_name = f"{name}:{idx}"
                    
                    if self.chunk_db.chunk_exists(chunk_name):
                        continue
                    
                    # For the chunk, get embedding (single call)
                    chunk_embedding = self.get_embedding(chunk_text)
                    # Summaries for each chunk as needed
                    chunk_summary = self.generate_summary(chunk_text)
                    
                    self.chunk_db.add_chunk(
                        chunk_name=chunk_name,
                        file_id=file_id,
                        puretext=chunk_text,
                        summary=chunk_summary,
                        embedding=chunk_embedding,
                        file_name_embedding=self.get_embedding(chunk_name)
                    )
        
        return {
            "file_ids": file_ids,
            "stats": stats
        }
    
    def get_embedding(self, text: str) -> List[float]:
        """
        Get embedding for a text string using the EmbeddingManager.

        Args:
            text: Text to embed.

        Returns:
            Embedding vector.
        """
        return self.embedding_manager.get_embedding(text, model="text-embedding-3-small")
    
    def generate_summary(self, text: str) -> str:
        """
        Generate a summary for a text string.
        
        Args:
            text: Text to summarize.

        Returns:
            Summary text.
        """
        # Truncate text if too long
        if len(text) > 4000:
            text = text[:4000]
        
        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system", 
                    "content": "You are a helpful assistant that summarizes text."
                },
                {
                    "role": "user", 
                    "content": f"Please summarize the following text in a concise paragraph:\n\n{text}"
                }
            ],
            max_tokens=300
        )
        
        return response.choices[0].message.content