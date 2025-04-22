"""
Script to run a simple test with the BRIGHT dataset.
"""

import os
import json
import argparse
from lorag import LORAG
from lorag.utils import write_file

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

def test_lorag_with_bright(example, documents, search_mode="all", n_return=5, effort=2):
    """
    Test LORAG with a single example from the BRIGHT dataset.
    
    Args:
        example: The example to test
        documents: The documents to search
        search_mode: Search mode to use
        n_return: Number of results to return
        effort: Effort level to use
        
    Returns:
        Dictionary containing test results
    """
    # Initialize LORAG
    lorag = LORAG(api_key=os.getenv("OPENAI_API_KEY"))
    
    # Add documents to LORAG
    doc_id_to_file_id = {}
    for doc in documents:
        doc_id = doc['id']
        content = doc['content']
        
        # Add document to LORAG
        file_id = lorag.add_text(content, f"bright_doc_{doc_id}")
        
        # Store mapping
        doc_id_to_file_id[doc_id] = file_id
    
    # Get query and gold IDs
    query = example['query']
    gold_ids = example['gold_ids']
    
    # Search using LORAG
    search_results = lorag.search(
        query=query,
        search_mode=search_mode,
        n_return=n_return,
        effort=effort
    )
    
    # Extract result file names
    result_files = []
    for result in search_results['results']:
        file_name = result['file_name']
        similarity = result.get('weighted_score', result.get('similarity', 0))
        content = result['content'][:200] + "..." if len(result['content']) > 200 else result['content']
        
        result_files.append({
            "file_name": file_name,
            "similarity": similarity,
            "content": content
        })
    
    # Convert gold IDs to LORAG file names
    gold_file_names = [f"bright_doc_{doc_id}" for doc_id in gold_ids]
    
    # Check if gold documents are in results
    gold_in_results = [file_info["file_name"] in gold_file_names for file_info in result_files]
    
    return {
        "query": query,
        "gold_ids": gold_ids,
        "gold_file_names": gold_file_names,
        "results": result_files,
        "gold_in_results": gold_in_results,
        "hit": any(gold_in_results)
    }

def main():
    """Main function to test LORAG with the BRIGHT dataset."""
    parser = argparse.ArgumentParser(description="Test LORAG with the BRIGHT dataset")
    parser.add_argument("--category", type=str, default="biology", help="Category of the BRIGHT dataset to test")
    parser.add_argument("--example_id", type=int, default=0, help="ID of the example to test")
    parser.add_argument("--data_dir", type=str, default="data/bright", help="Directory containing the dataset")
    parser.add_argument("--search_mode", type=str, default="all", choices=["all", "raw", "smart", "order"], help="Search mode to use")
    parser.add_argument("--n_return", type=int, default=5, help="Number of results to return")
    parser.add_argument("--effort", type=int, default=2, help="Effort level to use")
    args = parser.parse_args()
    
    # Load example and documents
    data = load_bright_example(args.category, args.example_id, args.data_dir)
    
    # Test LORAG
    results = test_lorag_with_bright(
        example=data["example"],
        documents=data["documents"],
        search_mode=args.search_mode,
        n_return=args.n_return,
        effort=args.effort
    )
    
    # Print results
    print("\nTest Results:")
    print(f"Query: {results['query']}")
    print(f"Gold Document IDs: {results['gold_ids']}")
    print(f"Gold File Names: {results['gold_file_names']}")
    print(f"Hit: {results['hit']}")
    
    print("\nSearch Results:")
    for i, result in enumerate(results['results']):
        is_gold = result['file_name'] in results['gold_file_names']
        gold_marker = "✓" if is_gold else " "
        print(f"{i+1}. [{gold_marker}] {result['file_name']} (Similarity: {result['similarity']:.4f})")
        print(f"   Content: {result['content']}")
        print()

if __name__ == "__main__":
    main()