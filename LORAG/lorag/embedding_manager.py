import os
import json
import numpy as np
from typing import List, Dict, Any, Optional, Union, Tuple
from openai import OpenAI
from sentence_transformers import SentenceTransformer
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings

class EmbeddingManager:
    """Manager for generating and working with embeddings."""
    
    def __init__(self, 
            api_key: str = "",
            model_name: str = "text-embedding-3-small",
            local_model:bool = False,
            ):
        """Initialize the embedding manager.
        
        Args:
            api_key: OpenAI API key
        """
        self.api_key = api_key
        self.local_model = local_model
        if local_model:
            self.model_name = model_name
            # Define the directory where the model is saved

            # Load the model
            self.model_object = SentenceTransformer(model_name)
            self.client = None
        else:
            self.model_name = model_name
            self.model_object = None
            self.client = OpenAI(api_key=api_key)
        
    
    def get_embedding(self, text: str, model: str = "text-embedding-3-small") -> List[float]:
        """Get embedding for a text string.
        
        One should call get_embedding_batch() for batch processing.
        
        Args:
            text: Text to embed
            model: Embedding model to use
            
        Returns:
            Embedding vector
        """
        if self.local_model:
            response = model.encode(text, convert_to_tensor=True)
            
        else:
            response = self.client.embeddings.create(
                model=model,
                input=text,
                encoding_format="float"
            )
            response = response.data[0].embedding
        return 
    
    def get_embedding_parallel(self, texts: List[str], model_name: str = "text-embedding-3-small", num_workers: int = 4) -> List[Union[List[float], None]]:
        def process_text(text: str) -> Union[List[float], None]:
            try:
                if self.local_model:
                    return self.model_object.encode(text, convert_to_tensor=False).tolist()
                else:
                    response = self.client.embeddings.create(
                        model=model_name,
                        input=text,
                        encoding_format="float"
                    )
                    return response.data[0].embedding
            except Exception as e:
                warnings.warn(f"Failed to compute embedding for text: {text}. Error: {e}")
                return None
        
        results = []
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            future_to_text = {executor.submit(process_text, text): text for text in texts}
            for future in as_completed(future_to_text):
                text = future_to_text[future]
                try:
                    result = future.result()
                    if result is None:
                        # Retry once if failed
                        result = process_text(text)
                except Exception as e:
                    warnings.warn(f"Failed to retry embedding for text: {text}. Error: {e}")
                    result = None
                
                results.append(result)
        
        return results
    
    
    
    def get_embedding_batch(self, texts: List[str]="", batch_input_file="batch_input_file") -> Dict[str, List[float]]:
        """Get embeddings for a batch of text strings using Batch API.
        
        Args:
            texts: List of texts to embed, if empty will try reading file as is
            model: Embedding model to use
            
        Returns:
            Dictionary of custom_id to embedding vector
        """
        # Prepare the input file
        batch_input_file = "batch_input.jsonl"
        with open(batch_input_file, 'w') as f:
            for i, text in enumerate(texts):
                json_line = json.dumps({
                    "custom_id": f"request-{i+1}",
                    "method": "POST",
                    "url": "/v1/embeddings",
                    "body": {
                        "model": self.model_name,
                        "input": text,
                        "encoding_format": "float"
                    }
                })
                f.write(json_line + '\n')

        # Upload the file
        file_details = self.client.files.create(
            file=open(batch_input_file, "rb"),
            purpose="batch"
        )
        
        # Create the batch
        batch = self.client.batches.create(
            input_file_id=file_details.id,
            endpoint="/v1/embeddings",
            completion_window="24h"
        )

        # Wait for batch to complete (in practice, use a properly timed loop or webhook)
        import time
        while True:
            retrieved_batch = self.client.batches.retrieve(batch.id)
            if retrieved_batch.status == "completed":
                break
            elif retrieved_batch.status in ["failed", "expired"]:
                raise Exception("Batch failed or expired.")
            time.sleep(10)  # Sleep before re-checking

        # Retrieve the results
        output_file = self.client.files.content(retrieved_batch.output_file_id)

        # Read and parse the output JSONL
        embeddings = {}
        for line in output_file.text.splitlines():
            result = json.loads(line)
            custom_id = result["custom_id"]
            embedding = result["response"]["body"]["data"][0]["embedding"]
            embeddings[custom_id] = embedding
        
        return embeddings
    
    def calculate_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Calculate cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Cosine similarity score
        """
        embedding1_np = np.array(embedding1, dtype=np.float32)
        embedding2_np = np.array(embedding2, dtype=np.float32)
        
        similarity = np.dot(embedding1_np, embedding2_np) / (
            np.linalg.norm(embedding1_np) * np.linalg.norm(embedding2_np)
        )
        
        return float(similarity)
    
    def embedding_to_blob(self, embedding: List[float]) -> bytes:
        """Convert embedding list to binary blob for storage.
        
        Args:
            embedding: Embedding vector
            
        Returns:
            Binary blob
        """
        return np.array(embedding, dtype=np.float32).tobytes()
    
    def blob_to_embedding(self, blob: bytes) -> List[float]:
        """Convert binary blob to embedding list.
        
        Args:
            blob: Binary blob
            
        Returns:
            Embedding vector
        """
        return np.frombuffer(blob, dtype=np.float32).tolist()
    
    
if __name__ == "__main__":
    print("Starting the embedding manager...")  # Initial check

    embedding_manager = EmbeddingManager(model_name="./model/raw", local_model=True)
    
    # Example texts
    texts = ["Hello world", "This is a test", "OpenAI is amazing"]
    
    try:
        # Get embeddings in parallel
        embeddings = embedding_manager.get_embedding_parallel(texts)
        print("Embeddings computation completed.")
    except Exception as error:
        print(f"An error occurred: {error}")

    # Print the results if available
    if embeddings:
        for text, embedding in zip(texts, embeddings):
            print(f"Text: {text}")
            print(f"Embedding: {embedding}")
            print()