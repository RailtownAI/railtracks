"""
Evaluation script for the BRIGHT dataset without using the OpenAI API.
"""

import os
import json
import argparse
import numpy as np
from tqdm import tqdm

def load_bright_dataset(category="biology", data_dir="data/bright"):
    """
    Load the prepared BRIGHT dataset.
    
    Args:
        category: The category of the BRIGHT dataset to load
        data_dir: The directory containing the dataset
        
    Returns:
        Dictionary containing the dataset
    """
    category_dir = os.path.join(data_dir, category)
    
    # Load examples
    with open(os.path.join(category_dir, "examples.json"), "r") as f:
        examples = json.load(f)
    
    # Load documents
    with open(os.path.join(category_dir, "documents.json"), "r") as f:
        documents = json.load(f)
    
    return {
        "examples": examples,
        "documents": documents
    }

def simple_search(query, documents, n_return=10):
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

def evaluate_dataset(examples, documents, n_return=10):
    """
    Evaluate the dataset using simple search.
    
    Args:
        examples: List of examples to evaluate
        documents: List of documents to search
        n_return: Number of results to return
        
    Returns:
        Dictionary containing evaluation results
    """
    results = {
        "queries": [],
        "metrics": {
            "mrr": [],
            "recall@1": [],
            "recall@3": [],
            "recall@5": [],
            "recall@10": []
        }
    }
    
    for example in tqdm(examples, desc="Evaluating queries"):
        query = example['query']
        gold_ids = example['gold_ids']
        
        # Skip if no gold IDs
        if not gold_ids:
            continue
        
        # Search for documents
        search_results = simple_search(query, documents, n_return)
        
        # Extract result document IDs
        result_ids = [result['doc_id'] for result in search_results]
        
        # Calculate metrics
        # MRR (Mean Reciprocal Rank)
        mrr = 0
        for i, doc_id in enumerate(result_ids):
            if doc_id in gold_ids:
                mrr = 1.0 / (i + 1)
                break
        
        # Recall@k
        recall_at_1 = sum(1 for doc_id in result_ids[:1] if doc_id in gold_ids) / len(gold_ids)
        recall_at_3 = sum(1 for doc_id in result_ids[:3] if doc_id in gold_ids) / len(gold_ids)
        recall_at_5 = sum(1 for doc_id in result_ids[:5] if doc_id in gold_ids) / len(gold_ids)
        recall_at_10 = sum(1 for doc_id in result_ids[:10] if doc_id in gold_ids) / len(gold_ids)
        
        # Store results
        results["queries"].append({
            "id": example['id'],
            "query": query,
            "gold_ids": gold_ids,
            "result_ids": result_ids,
            "mrr": mrr,
            "recall@1": recall_at_1,
            "recall@3": recall_at_3,
            "recall@5": recall_at_5,
            "recall@10": recall_at_10
        })
        
        # Update metrics
        results["metrics"]["mrr"].append(mrr)
        results["metrics"]["recall@1"].append(recall_at_1)
        results["metrics"]["recall@3"].append(recall_at_3)
        results["metrics"]["recall@5"].append(recall_at_5)
        results["metrics"]["recall@10"].append(recall_at_10)
    
    # Calculate average metrics
    results["metrics"]["avg_mrr"] = np.mean(results["metrics"]["mrr"])
    results["metrics"]["avg_recall@1"] = np.mean(results["metrics"]["recall@1"])
    results["metrics"]["avg_recall@3"] = np.mean(results["metrics"]["recall@3"])
    results["metrics"]["avg_recall@5"] = np.mean(results["metrics"]["recall@5"])
    results["metrics"]["avg_recall@10"] = np.mean(results["metrics"]["recall@10"])
    
    return results

def main():
    """Main function to evaluate on the BRIGHT dataset."""
    parser = argparse.ArgumentParser(description="Evaluate on the BRIGHT dataset")
    parser.add_argument("--category", type=str, default="biology", help="Category of the BRIGHT dataset to evaluate")
    parser.add_argument("--data_dir", type=str, default="data/bright", help="Directory containing the dataset")
    parser.add_argument("--output_dir", type=str, default="data/bright_results", help="Directory to save results")
    parser.add_argument("--n_return", type=int, default=10, help="Number of results to return")
    parser.add_argument("--example_ids", type=str, default="", help="Comma-separated list of example IDs to evaluate (empty for all)")
    args = parser.parse_args()
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Load dataset
    dataset = load_bright_dataset(args.category, args.data_dir)
    
    # Filter examples if specific IDs are provided
    if args.example_ids:
        example_ids = args.example_ids.split(",")
        dataset["examples"] = [ex for ex in dataset["examples"] if ex["id"] in example_ids]
    
    # Evaluate dataset
    results = evaluate_dataset(
        examples=dataset["examples"],
        documents=dataset["documents"],
        n_return=args.n_return
    )
    
    # Save results
    results_file = os.path.join(args.output_dir, f"results_{args.category}_simple.json")
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)
    
    # Print summary
    print("\nEvaluation Results:")
    print(f"Category: {args.category}")
    print(f"Number of Queries: {len(results['queries'])}")
    print(f"MRR: {results['metrics']['avg_mrr']:.4f}")
    print(f"Recall@1: {results['metrics']['avg_recall@1']:.4f}")
    print(f"Recall@3: {results['metrics']['avg_recall@3']:.4f}")
    print(f"Recall@5: {results['metrics']['avg_recall@5']:.4f}")
    print(f"Recall@10: {results['metrics']['avg_recall@10']:.4f}")
    print(f"Results saved to {results_file}")

if __name__ == "__main__":
    main()