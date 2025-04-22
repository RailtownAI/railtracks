"""
Simple test script for the LORAG system.
"""

import os
import json
from openai import OpenAI
# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_embedding(text):
    """Get embedding for a text string."""
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
        encoding_format="float"
    )
    return response.data[0].embedding

def generate_summary(text):
    """Generate a summary for a text."""
    # Limit text length for summarization
    if len(text) > 8000:
        text = text[:8000] + "..."
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that generates concise summaries of text."},
            {"role": "user", "content": f"Please summarize the following text in a few sentences:\n\n{text}"}
        ]
    )
    
    return response.choices[0].message.content

def search_by_similarity(query, documents):
    """Search for documents by similarity to query."""
    import numpy as np
    
    # Get embedding for query
    query_embedding = get_embedding(query)
    query_embedding_np = np.array(query_embedding)
    
    # Calculate similarity for each document
    results = []
    
    for doc in documents:
        doc_embedding_np = np.array(doc['embedding'])
        
        # Calculate cosine similarity
        similarity = np.dot(query_embedding_np, doc_embedding_np) / (
            np.linalg.norm(query_embedding_np) * np.linalg.norm(doc_embedding_np)
        )
        
        results.append({
            'document': doc,
            'similarity': float(similarity)
        })
    
    # Sort by similarity (descending)
    results.sort(key=lambda x: x['similarity'], reverse=True)
    
    return results

def main():
    """Test the LORAG system."""
    # Sample documents
    documents = [
        {
            'name': 'python_basics',
            'content': """
            Python is a high-level, interpreted programming language known for its readability and simplicity.
            
            Key features of Python include:
            
            1. Easy to learn and use: Python has a simple syntax that emphasizes readability, making it an excellent language for beginners.
            
            2. Interpreted language: Python code is executed line by line, which makes debugging easier.
            
            3. Dynamically typed: You don't need to declare variable types, as Python determines them at runtime.
            
            4. Object-oriented: Python supports object-oriented programming paradigms, allowing for code reuse and modularity.
            
            5. Extensive standard library: Python comes with a large standard library that includes modules for various tasks like file I/O, system calls, and web services.
            
            6. Cross-platform: Python runs on various operating systems, including Windows, macOS, and Linux.
            
            Common uses of Python include web development, data analysis, artificial intelligence, scientific computing, automation, and more.
            """
        },
        {
            'name': 'machine_learning',
            'content': """
            Machine Learning is a subset of artificial intelligence that focuses on developing systems that can learn from and make decisions based on data.
            
            Key concepts in Machine Learning include:
            
            1. Supervised Learning: The algorithm learns from labeled training data, making predictions or decisions based on that data.
            
            2. Unsupervised Learning: The algorithm finds patterns in unlabeled data.
            
            3. Reinforcement Learning: The algorithm learns by interacting with an environment and receiving rewards or penalties.
            
            4. Neural Networks: Computing systems inspired by the human brain's neural networks, used for deep learning.
            
            5. Feature Engineering: The process of selecting and transforming variables to improve model performance.
            
            Popular Machine Learning libraries in Python include TensorFlow, PyTorch, scikit-learn, and Keras.
            
            Applications of Machine Learning include image and speech recognition, natural language processing, recommendation systems, and autonomous vehicles.
            """
        },
        {
            'name': 'lorag_description',
            'content': """
            LORAG (Layered or Hybrid RAG) is a flexible system that combines multiple search and retrieval methods.
            
            It can be configured in various "modes" to adapt to different use cases and resource constraints:
            
            1. "all" mode: Execute and return the results from all available search methods.
            
            2. "raw" mode: Similar to "all", but returns raw data along with intermediate scores.
            
            3. "smart" mode: The system asks an AI layer to consider the weighted outputs from each method.
            
            4. "order" mode: Search methods are used in a specific order, starting with faster methods.
            
            LORAG supports multiple search methods, including embedding-based search, file name lookup, summary-based search, regex search, and more.
            """
        }
    ]
    
    # Generate embeddings and summaries for documents
    for doc in documents:
        doc['embedding'] = get_embedding(doc['content'])
        doc['summary'] = generate_summary(doc['content'])
        print(f"Processed document: {doc['name']}")
        print(f"Summary: {doc['summary']}")
    
    # Test queries
    test_queries = [
        "What is Python used for?",
        "Explain machine learning concepts",
        "What is LORAG and how does it work?"
    ]
    
    for query in test_queries:
        print(f"\nQuery: {query}")
        
        # Search for documents
        results = search_by_similarity(query, documents)
        
        # Print top result
        if results:
            top_result = results[0]
            print(f"Top result: {top_result['document']['name']}")
            print(f"Similarity: {top_result['similarity']:.4f}")
            print(f"Summary: {top_result['document']['summary']}")
        else:
            print("No results found.")
    
    print("\nSimple test completed successfully!")

if __name__ == "__main__":
    main()