"""
Script to evaluate LORAG on the BRIGHT dataset.
"""

import os
import json
import argparse
import numpy as np
from tqdm import tqdm
import sys 
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from lorag import LORAG
from lorag.utils import write_file



def index_bright_documents(lorag:LORAG, documents, output_dir="data/bright_index"):
    """
    Index the BRIGHT documents in LORAG.
    
    Args:
        lorag: LORAG instance
        documents: List of documents to index
        output_dir: Directory to store document information
        
    Returns:
        Dictionary mapping document IDs to LORAG file IDs
    """
    os.makedirs(output_dir, exist_ok=True)
    
    doc_id_to_file_id = {}
    
    for doc in tqdm(documents, desc="Indexing documents"):
        doc_id = doc['id']
        content = doc['content']
        
        # Add document to LORAG
        file_id = lorag.add_text(content, f"bright_doc_{doc_id}")
        
        # Store mapping
        doc_id_to_file_id[doc_id] = file_id
    
    # Save mapping
    with open(os.path.join(output_dir, "doc_id_to_file_id.json"), "w") as f:
        json.dump(doc_id_to_file_id, f, indent=2)
    
    return doc_id_to_file_id

def evaluate_lorag(lorag, examples, doc_id_to_file_id, search_mode="all", n_return=10, effort=2):
    """
    Evaluate LORAG on the BRIGHT dataset.
    
    Args:
        lorag: LORAG instance
        examples: List of examples to evaluate
        doc_id_to_file_id: Mapping from document IDs to LORAG file IDs
        search_mode: Search mode to use
        n_return: Number of results to return
        effort: Effort level to use
        
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
            result_files.append(file_name)
        
        # Convert gold IDs to LORAG file names
        gold_file_names = [f"bright_doc_{doc_id}" for doc_id in gold_ids]
        
        # Calculate metrics
        # MRR (Mean Reciprocal Rank)
        mrr = 0
        for i, file_name in enumerate(result_files):
            if file_name in gold_file_names:
                mrr = 1.0 / (i + 1)
                break
        
        # Recall@k
        recall_at_1 = sum(1 for file_name in result_files[:1] if file_name in gold_file_names) / len(gold_file_names)
        recall_at_3 = sum(1 for file_name in result_files[:3] if file_name in gold_file_names) / len(gold_file_names)
        recall_at_5 = sum(1 for file_name in result_files[:5] if file_name in gold_file_names) / len(gold_file_names)
        recall_at_10 = sum(1 for file_name in result_files[:10] if file_name in gold_file_names) / len(gold_file_names)
        
        # Store results
        results["queries"].append({
            "id": example['id'],
            "query": query,
            "gold_ids": gold_ids,
            "gold_file_names": gold_file_names,
            "result_files": result_files,
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
    """Main function to evaluate LORAG on the BRIGHT dataset."""
    parser = argparse.ArgumentParser(description="Evaluate LORAG on the BRIGHT dataset")
    parser.add_argument("--category", type=str, default="biology", help="Category of the BRIGHT dataset to evaluate")
    parser.add_argument("--data_dir", type=str, default="data/bright", help="Directory containing the dataset")
    parser.add_argument("--output_dir", type=str, default="data/bright_results", help="Directory to save results")
    parser.add_argument("--search_mode", type=str, default="all", choices=["all", "raw", "smart", "order"], help="Search mode to use")
    parser.add_argument("--n_return", type=int, default=10, help="Number of results to return")
    parser.add_argument("--effort", type=int, default=2, help="Effort level to use")
    parser.add_argument("--example_ids", type=str, default="0,100,1000", help="Comma-separated list of example IDs to evaluate")
    args = parser.parse_args()
    
    # Parse example IDs
    example_ids = [int(x) for x in args.example_ids.split(",")]
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Load dataset
    dataset = load_bright_dataset(args.category, args.data_dir)
    
    example_id_str = [f"{ex['id']}" for ex in dataset["examples"]]
    
    # Filter examples if specific IDs are provided
    if example_ids:
        dataset["examples"] = [ex for ex in dataset["examples"] if ex["id"] in example_id_str]
    
    # Initialize LORAG
    lorag = LORAG(api_key=os.getenv("OPENAI_API_KEY"))
    
    # Index documents
    doc_id_to_file_id = index_bright_documents(lorag, dataset["documents"], os.path.join(args.output_dir, "index"))
    
    # Evaluate LORAG
    results = evaluate_lorag(
        lorag=lorag,
        examples=dataset["examples"],
        doc_id_to_file_id=doc_id_to_file_id,
        search_mode=args.search_mode,
        n_return=args.n_return,
        effort=args.effort
    )
    
    # Save results
    results_file = os.path.join(args.output_dir, f"results_{args.category}_{args.search_mode}.json")
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)
    
    # Print summary
    print("\nEvaluation Results:")
    print(f"Category: {args.category}")
    print(f"Search Mode: {args.search_mode}")
    print(f"Number of Queries: {len(results['queries'])}")
    print(f"MRR: {results['metrics']['avg_mrr']:.4f}")
    print(f"Recall@1: {results['metrics']['avg_recall@1']:.4f}")
    print(f"Recall@3: {results['metrics']['avg_recall@3']:.4f}")
    print(f"Recall@5: {results['metrics']['avg_recall@5']:.4f}")
    print(f"Recall@10: {results['metrics']['avg_recall@10']:.4f}")
    print(f"Results saved to {results_file}")

if __name__ == "__main__":
    main()