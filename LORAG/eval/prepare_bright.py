"""
Script to prepare the BRIGHT dataset for use with LORAG.
"""

import os
import json
import random
from datasets import load_dataset
from tqdm import tqdm

def download_bright_dataset(category="biology", sample_indices=[], noise_num=100, type="long"):
    """
    Download and prepare the BRIGHT dataset for use with LORAG.
    
    Args:
        category: The category of the BRIGHT dataset to download
        sample_indices: The indices of the examples to use, if not provides, all
        noise_num: The number of noise documents to include
        
    Returns:
        Dictionary containing the prepared dataset
    """
    print(f"# Downloading BRIGHT dataset for category: {category} (Might take a while)")
    
    # Load the dataset
    examples = load_dataset('xlangai/BRIGHT', 'examples', split=category)
    if type == "short":
        documents = load_dataset('xlangai/BRIGHT', 'documents', split=category)
    else:
        documents = load_dataset('xlangai/BRIGHT', 'long_documents', split=category)
    
    # Convert to lists for easier manipulation
    examples_list = list(examples)
    documents_list = list(documents)
    print(f"# {len(examples_list)} examples and {len(documents_list)} documents downloaded")
    
    # to list of string
    sample_indices_string = [str(i) for i in sample_indices]
    if sample_indices:
        # Filter examples to only include the specified indices
        filtered_examples = [ex for ex in examples_list if ex['id'] in sample_indices_string]
    else:
        # If no sample indices provided, use all examples
        filtered_examples = examples_list
    
    if not filtered_examples:
        print(f"Warning: No examples found with indices {sample_indices}")
        # error out
        raise ValueError(f"No examples found with indices {sample_indices}")
    
    prepared_data = {
        "examples": [],
    }
    if type == "long":
        prepared_data ["long_documents"] = []
    if type == "short":
        prepared_data ["documents"] = []
        
    print(f"# {len(filtered_examples)}/{len(examples_list)} examples filtered")
    # set
    gold_document_list = []
    # Process each example
    for example in filtered_examples:
        # Get the gold document IDs
        gold_ids = example.get('gold_ids', [])
        
        # Find the gold documents for this example
        gold_documents = [doc for doc in documents_list if doc['id'] in gold_ids]
        # add to set
        for doc in gold_documents:
            # if not part, add
            if doc not in gold_document_list:
                gold_document_list.append(doc)
        
        # Add to prepared data
        prepared_data["examples"].append(example)
    # set
    noise_document_list = []
    # Add noise documents, which is not in gold documents
    remaining_documents = [doc for doc in documents_list if doc not in gold_document_list]
    # Randomly select noise documents
    if len(remaining_documents) > noise_num:
        noise_documents = random.sample(remaining_documents, noise_num)
    else:
        noise_documents = remaining_documents
    # Add noise documents to the prepared data
    for doc in noise_documents:
        if doc not in noise_document_list:
            # add to set
            noise_document_list.append(doc)
        else:
            print(f"I saw duplicate but it should not happen, something is wrong")
            raise ValueError(f"Duplicate document found: {doc['id']}")
        
    # noise + gold
    # both is set so no overlap
    save_document_list = list(gold_document_list) + list(noise_document_list)
    # save
    for doc in save_document_list:
        if type == "long":
            if doc not in prepared_data["long_documents"]:
                prepared_data["long_documents"].append(doc)
        if type == "short":
            if doc not in prepared_data["documents"]:
                prepared_data["documents"].append(doc)
    print(
        f"# {len(save_document_list)}/{len(documents_list)} documents added, ",
        f"out of which {len(gold_document_list)} are gold documents"
    )

    return prepared_data

def save_bright_dataset(data, output_dir="data/bright"):
    """
    Save the prepared BRIGHT dataset to disk.
    
    Args:
        data: The prepared dataset
        output_dir: The directory to save the dataset to
    """
    # check if output_dir exists, else create
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Save examples
    with open(os.path.join(output_dir, "examples.json"), "w") as f:
        json.dump(data["examples"], f, indent=2)
    
    # Save documents
    if "documents" in data:
        with open(os.path.join(output_dir, "documents.json"), "w") as f:
            json.dump(data["documents"], f, indent=2)
        
    # check if long_documents exist, if so save
    if "long_documents" in data:
        with open(os.path.join(output_dir, "long_documents.json"), "w") as f:
            json.dump(data["long_documents"], f, indent=2)
    
    print(f"Saved dataset to {output_dir}")
    

def main():
    """Main function to prepare the BRIGHT dataset."""
    # Create output directory
    output_dir = "data/bright"
    
    # Categories to download
    categories = ["biology", "stackoverflow", "robotics"]
    
    # Sample indices to use
    sample_indices = [0, 10, 100]
    
    # Number of documents to include
    num_docs = 100
    
    for category in categories:
        data = download_bright_dataset(category, sample_indices, num_docs)
        category_dir = os.path.join(output_dir, category)
        save_bright_dataset(data, category_dir)
        
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

if __name__ == "__main__":
    main()