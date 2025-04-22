"""
Text processing module for LORAG.

This module provides functionality for processing text, including chunking and summarization.
"""

import os
from typing import List, Dict, Any, Optional, Union, Tuple
from openai import OpenAI
# print sys.path
import sys
print(sys.path)
from lorag.utils import LORAGTokenizer
from lorag.logger import logger
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings

class TextProcessor:
    """Processor for text operations."""
    
    def __init__(self, api_key: str):
        """Initialize the text processor.
        
        Args:
            api_key: OpenAI API key
        """
        self.api_key = api_key
        self.client = OpenAI(api_key=api_key)
        
    def chunk_text(self, text: str, 
                    chunk_size: int, 
                    chunk_overlap: int) -> List[str]:
        """
        Split text into chunks by character count.

        TODO: use LLM to do this
        """
        chunks = []
        start = 0
        
        # end was used but never declared in the original code snippet;
        # we'll add a separate approach or define end before the loop.
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk = text[start:end]
            chunks.append(chunk)
            start += chunk_size - chunk_overlap
        
        return chunks
    
    def chunk_text_token(self, text: str, 
                          chunk_size: int, 
                          chunk_overlap: int, 
                          token_encoding: str = "cl100k_base") -> List[str]:
        """
        Split text into chunks by token.

        TODO: use LLM to do this
        """
        chunks = []
        tokenizer = LORAGTokenizer(token_encoding)
        tokens = tokenizer.encode(text)

        if chunk_overlap > chunk_size:
            logger.warning(
                f"Warning: chunk_overlap ({chunk_overlap}) is greater than chunk_size ({chunk_size})."
                " Should be <= 40%"
            )
            raise ValueError("chunk_overlap should be less than or equal to chunk_size")
        
        start = 0
        while start < len(tokens):
            end = min(start + chunk_size, len(tokens))
            token_chunk = tokens[start:end]
            chunk = tokenizer.decode(token_chunk)
            
            chunks.append(chunk)
            start += chunk_size - chunk_overlap
            if end >= len(tokens):
                break
        
        return chunks
    
    def generate_summary(self, text: str, model: str = "gpt-4o") -> str:
        return self.generate_summary_parallel([text], model=model)[0]
    
    def generate_summary_parallel(self, texts: List[str], model: str = "gpt-4o", num_workers: int = 4) -> List[str]:
        def process_text(text: str) -> str:
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that generates concise summaries of text."},
                        {"role": "user", "content": f"Please summarize the following text in a few sentences:\n\n{text}"}
                    ]
                )
                return response.choices[0].message.content
            except Exception as e:
                warnings.warn(f"Failed to generate summary for text: {text}. Error: {e}")
                return None
        
        summaries = []
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            future_to_text = {executor.submit(process_text, text): text for text in texts}
            for future in as_completed(future_to_text):
                text = future_to_text[future]
                try:
                    summary = future.result()
                    if summary is None:
                        # Retry once if failed
                        summary = process_text(text)
                except Exception as e:
                    warnings.warn(f"Failed to retry summarization for text: {text}. Error: {e}")
                    summary = None
                
                summaries.append(summary)
        
        return summaries
        
    
    def gpt_request_batch(self, prompts: List, model: str = "gpt-3.5-turbo", batch_input_file="batch_input_file") -> Dict[str, str]:
        """Get GPT responses for a batch of prompt pieces using a Batch API.
        
        Args:
            prompts: List of prompts to send
            model: GPT model to use
            
        Returns:
            Dictionary of custom_id to GPT response
        """
        # Global prompt template
        prompt_base = "This is a template with {key1} and {key2}."

        # Prepare the input file
        batch_input_file = "batch_input.jsonl"
        with open(batch_input_file, 'w') as f:
            for i, prompt in enumerate(prompts):
                # Create the actual prompt by substituting the placeholders

                json_line = json.dumps({
                    "custom_id": f"request-{i+1}",
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": model,
                        "messages": [{"role": "system", "content": "You are an helpful assistant."}, {"role": "user", "content": prompt}],
                        "max_tokens": 1000,
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
            endpoint="/v1/chat/completions",
            completion_window="24h"
        )

        # Wait for batch to complete (in practice, use a properly timed loop or webhook)
        import time
        while True:
            print("-", end="")
            retrieved_batch = self.client.batches.retrieve(batch.id)
            if retrieved_batch.status == "completed":
                break
            elif retrieved_batch.status in ["failed", "expired"]:
                raise Exception("Batch failed or expired.")
            time.sleep(5)  # Sleep before re-checking

        # Retrieve the results
        output_file = self.client.files.content(retrieved_batch.output_file_id)

        # Read and parse the output JSONL
        responses = {}
        for line in output_file.text.splitlines():
            result = json.loads(line)
            custom_id = result["custom_id"]
            response_text = result["response"]["body"]["choices"][0]["message"]["content"]
            responses[custom_id] = response_text
        
        return responses
    
    
    
if __name__ == "__main__":
    
    text_1 = "This is a test text, return 123" 
    text_2 = "This is a small test text. return 123" 
    import sys
    import os
    # Example usage
    text_processor = TextProcessor(api_key=os.environ.get("OPENAI_API_KEY"))
    
    # Chunking example
    text = "This is a long text that needs to be chunked into smaller pieces."
    chunks = text_processor.chunk_text(text, chunk_size=20, chunk_overlap=5)
    print("Chunks:", chunks)
    
    # Summarization example
    summary = text_processor.gpt_request_batch([text_1, text_2], model="gpt-3.5-turbo")
    print("Summary:", summary)
    