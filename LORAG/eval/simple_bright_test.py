"""
Simple test script for the BRIGHT dataset without using the OpenAI API.
"""

import os
import json
import argparse
import numpy as np
from tqdm import tqdm

def load_bright_example(category="biology", example_id=0, data_dir="data/bright"):
    """
    Load a single example from the BRIGHT dataset.
    
    Args:
        category: The category of the BRIGHT dataset to load
        example_id: The ID of the example to load
        data_dir: The directory containing the dataset
        
    Returns:
        Dictionary containing the example and its documents
    """
    category_dir = os.path.join(data_dir, category)
    
    # Load examples
    with open(os.path.join(category_dir, "examples.json"), "r") as f:
        examples = json.load(f)
    
    # Load documents
    with open(os.path.join(category_dir, "documents.json"), "r") as f:
        documents = json.load(f)
    
    # Find the example with the specified ID (convert to string for comparison)
    example = next((ex for ex in examples if ex["id"] == str(example_id)), None)
    
    if example is None:
        raise ValueError(f"Example with ID {example_id} not found")
    
    return {
        "example": example,
        "documents": documents
    }

def simple_search(query, documents, n_return=5):
    """
    Simple search function using word overlap.
    
    Args:
        query: The search query
        documents: The documents to search
        n_return: Number of results to return
        
    Returns:
        List of search results
    """
    # Tokenize query
    query_words = set(query.lower().split())
    
    # Calculate overlap for each document
    results = []
    for doc in documents:
        doc_id = doc['id']
        content = doc['content']
        
        # Tokenize document
        doc_words = set(content.lower().split())
        
        # Calculate overlap
        overlap = len(query_words.intersection(doc_words))
        
        # Calculate similarity score
        similarity = overlap / max(len(query_words), 1)
        
        results.append({
            "doc_id": doc_id,
            "content": content,
            "similarity": similarity
        })
    
    # Sort by similarity (descending)
    results.sort(key=lambda x: x['similarity'], reverse=True)
    
    # Return top N results
    return results[:n_return]

def main():
    """Main function to test with the BRIGHT dataset."""
    parser = argparse.ArgumentParser(description="Test with the BRIGHT dataset")
    parser.add_argument("--category", type=str, default="biology", help="Category of the BRIGHT dataset to test")
    parser.add_argument("--example_id", type=int, default=0, help="ID of the example to test")
    parser.add_argument("--data_dir", type=str, default="data/bright", help="Directory containing the dataset")
    parser.add_argument("--n_return", type=int, default=5, help="Number of results to return")
    args = parser.parse_args()
    
    # Load example and documents
    data = load_bright_example(args.category, args.example_id, args.data_dir)
    
    # Get query and gold IDs
    query = data["example"]["query"]
    gold_ids = data["example"]["gold_ids"]
    
    # Search for documents
    results = simple_search(query, data["documents"], args.n_return)
    
    # Check if gold documents are in results
    gold_in_results = [result["doc_id"] in gold_ids for result in results]
    
    # Print results
    print("\nTest Results:")
    print(f"Query: {query}")
    print(f"Gold Document IDs: {gold_ids}")
    print(f"Hit: {any(gold_in_results)}")
    
    print("\nSearch Results:")
    for i, result in enumerate(results):
        is_gold = result['doc_id'] in gold_ids
        gold_marker = "✓" if is_gold else " "
        print(f"{i+1}. [{gold_marker}] {result['doc_id']} (Similarity: {result['similarity']:.4f})")
        print(f"   Content: {result['content'][:200]}...")
        print()

if __name__ == "__main__":
    main()