"""
Sample script to demonstrate the LORAG system.
"""

import os
import json
import argparse
from lorag import LORAG
from lorag.utils import write_file

def get_api_key():
    """Get API key from environment variable or command line."""
    parser = argparse.ArgumentParser(description="Demonstrate LORAG system")
    parser.add_argument("--api_key", type=str, help="OpenAI API key")
    args = parser.parse_args()
    
    # Get API key from environment variable if not provided
    api_key = args.api_key or os.environ.get("OPENAI_API_KEY")
    
    if not api_key:
        print("Warning: No OpenAI API key provided. Using placeholder key.")
        api_key = "sk-placeholder-key"
    
    return api_key

# Get API key
API_KEY = get_api_key()

# Create data directory if it doesn't exist
os.makedirs("data", exist_ok=True)

# Initialize LORAG system
lorag = LORAG(api_key=API_KEY)

# Create sample text files
sample_texts = {
    "python_basics.txt": """
    Python is a high-level, interpreted programming language known for its readability and simplicity.
    
    Key features of Python include:
    
    1. Easy to learn and use: Python has a simple syntax that emphasizes readability, making it an excellent language for beginners.
    
    2. Interpreted language: Python code is executed line by line, which makes debugging easier.
    
    3. Dynamically typed: You don't need to declare variable types, as Python determines them at runtime.
    
    4. Object-oriented: Python supports object-oriented programming paradigms, allowing for code reuse and modularity.
    
    5. Extensive standard library: Python comes with a large standard library that includes modules for various tasks like file I/O, system calls, and web services.
    
    6. Cross-platform: Python runs on various operating systems, including Windows, macOS, and Linux.
    
    Common uses of Python include web development, data analysis, artificial intelligence, scientific computing, automation, and more.
    """,
    
    "machine_learning.txt": """
    Machine Learning is a subset of artificial intelligence that focuses on developing systems that can learn from and make decisions based on data.
    
    Key concepts in Machine Learning include:
    
    1. Supervised Learning: The algorithm learns from labeled training data, making predictions or decisions based on that data.
    
    2. Unsupervised Learning: The algorithm finds patterns in unlabeled data.
    
    3. Reinforcement Learning: The algorithm learns by interacting with an environment and receiving rewards or penalties.
    
    4. Neural Networks: Computing systems inspired by the human brain's neural networks, used for deep learning.
    
    5. Feature Engineering: The process of selecting and transforming variables to improve model performance.
    
    Popular Machine Learning libraries in Python include TensorFlow, PyTorch, scikit-learn, and Keras.
    
    Applications of Machine Learning include image and speech recognition, natural language processing, recommendation systems, and autonomous vehicles.
    """,
    
    "database_systems.txt": """
    Database systems are organized collections of data stored and accessed electronically.
    
    Types of database systems include:
    
    1. Relational Databases: Store data in tables with rows and columns. Examples include MySQL, PostgreSQL, and Oracle.
    
    2. NoSQL Databases: Non-relational databases designed for distributed data stores. Examples include MongoDB, Cassandra, and Redis.
    
    3. Graph Databases: Store data in nodes and edges. Examples include Neo4j and Amazon Neptune.
    
    4. Time-Series Databases: Optimized for time-stamped or time-series data. Examples include InfluxDB and TimescaleDB.
    
    Key concepts in database systems include:
    
    - ACID Properties: Atomicity, Consistency, Isolation, and Durability, which ensure reliable transaction processing.
    
    - SQL (Structured Query Language): A standard language for managing relational databases.
    
    - Indexing: A technique to optimize database performance by minimizing disk access.
    
    - Normalization: The process of organizing data to reduce redundancy and improve data integrity.
    
    Database systems are essential for applications that require data persistence, such as e-commerce platforms, content management systems, and financial applications.
    """
}

# Write sample text files
for filename, content in sample_texts.items():
    full_path = os.path.join("data", filename)
    write_file(full_path, content)
    print(f"Created sample file: {filename} at: {full_path}")

# Add files to LORAG system
file_ids = {}
for filename in sample_texts.keys():
    full_path = os.path.join("data", filename)
    result = lorag.add_file(full_path)
    file_id = result["file_id"]
    file_ids[filename] = file_id
    
    status = result["status"]
    chunks = result.get("chunks", {})
    
    if status == "added":
        print(f"Added {filename} to LORAG system with ID: {file_id}")
        print(f"  Chunks: {chunks.get('total', 0)} total, {chunks.get('added', 0)} added, {chunks.get('existing', 0)} existing")
    elif status == "existing":
        print(f"File {filename} already exists in LORAG system with ID: {file_id}")
    elif status == "updated":
        print(f"Updated {filename} in LORAG system with ID: {file_id}")
        print(f"  Chunks: {chunks.get('total', 0)} total, {chunks.get('added', 0)} added, {chunks.get('existing', 0)} existing")

# Add text directly to LORAG system
direct_text = """
Retrieval Augmented Generation (RAG) is a technique that combines retrieval-based and generation-based approaches in natural language processing.

RAG works by first retrieving relevant documents or passages from a knowledge base, then using those retrieved texts as additional context for a language model to generate a response.

Benefits of RAG include:

1. Improved accuracy: By providing relevant context, RAG helps language models generate more accurate and factual responses.

2. Reduced hallucination: RAG can help reduce the tendency of language models to generate false or made-up information.

3. Up-to-date information: RAG can access information that wasn't available during the language model's training.

4. Transparency: RAG can cite the sources of information used to generate responses.

RAG is commonly used in question-answering systems, chatbots, and other applications where factual accuracy is important.
"""

result = lorag.add_text(direct_text, "rag_explanation")
direct_text_id = result["file_id"]
status = result["status"]
chunks = result.get("chunks", {})

if status == "added":
    print(f"Added text directly to LORAG system with ID: {direct_text_id}")
    print(f"  Chunks: {chunks.get('total', 0)} total, {chunks.get('added', 0)} added, {chunks.get('existing', 0)} existing")
elif status == "existing":
    print(f"Text already exists in LORAG system with ID: {direct_text_id}")
elif status == "updated":
    print(f"Updated text in LORAG system with ID: {direct_text_id}")
    print(f"  Chunks: {chunks.get('total', 0)} total, {chunks.get('added', 0)} added, {chunks.get('existing', 0)} existing")

# Perform searches using different modes
print("\n=== Search Results ===\n")

# Search using "all" mode
query = "What is Python used for?"
results_all = lorag.search(query, search_mode="all", n_return=2)
print(f"Search Query: {query}")
print(f"Search Mode: all")
print(f"Results: {len(results_all['results'])}")
print(f"Methods Used: {results_all['methods_used']}")
print("\nTop Result:")
top_result = results_all['results'][0]
print(f"File: {top_result['file_name']}")
print(f"Similarity: {top_result['weighted_score']:.4f}")
print(f"Content: {top_result['content'][:200]}...\n")

# Search using "smart" mode
query = "Explain machine learning concepts"
results_smart = lorag.search(query, search_mode="smart", n_return=2, n_ai=2, n_out=1)
print(f"Search Query: {query}")
print(f"Search Mode: smart")
print(f"Results: {len(results_smart['results'])}")
print(f"Methods Used: {results_smart['methods_used']}")
print("\nTop Result:")
if results_smart['results']:
    top_result = results_smart['results'][0]
    print(f"File: {top_result['file_name']}")
    print(f"Similarity: {top_result.get('similarity', 0):.4f}")
    print(f"Content: {top_result['content'][:200]}...\n")
else:
    print("No results found.\n")

# Search using "order" mode
query = "What are database types?"
results_order = lorag.search(query, search_mode="order", n_return=2, effort=2)  # Increase effort level
print(f"Search Query: {query}")
print(f"Search Mode: order")
print(f"Results: {len(results_order['results'])}")
print(f"Methods Used: {results_order['methods_used']}")
print("\nTop Result:")
if results_order['results']:
    top_result = results_order['results'][0]
    print(f"File: {top_result['file_name']}")
    print(f"Similarity: {top_result.get('similarity', 0):.4f}")
    print(f"Content: {top_result['content'][:200]}...\n")
else:
    print("No results found.\n")

# Search for RAG information
query = "What is RAG and how does it work?"
results_rag = lorag.search(query, search_mode="all", n_return=1)
print(f"Search Query: {query}")
print(f"Search Mode: all")
print(f"Results: {len(results_rag['results'])}")
print(f"Methods Used: {results_rag['methods_used']}")
print("\nTop Result:")
if results_rag['results']:
    top_result = results_rag['results'][0]
    print(f"File: {top_result['file_name']}")
    print(f"Similarity: {top_result['weighted_score']:.4f}")
    print(f"Content: {top_result['content'][:200]}...\n")
else:
    print("No results found.\n")

# --- BUILD EMBEDDINGS ONCE ---
# from sample_rag_only import build_document_embeddings, retrieve_documents
# # In an actual application, you'd do this once at startup and possibly store/cache them
# doc_embeddings = build_document_embeddings(folder_path="data")

# # --- USAGE EXAMPLE ---
# user_question = "What are database types?"
# max_return = 3

# top_docs = retrieve_documents(user_question, doc_embeddings, max_return=max_return)

# print(f"RAG: Top {max_return} documents relevant to your question:")
# for i, (score, filename, text) in enumerate(top_docs, start=1):
#     print(f"\n{i}. {filename} (score: {score:.4f})")
#     # Optionally, show an excerpt of the text:
#     print(f"Excerpt: {text[:200]}...")

# Demonstrate batch processing
print("\n=== Batch Processing Demonstration ===\n")

# Create additional sample texts for batch processing
batch_texts = [
    {
        "name": "data_science",
        "content": """
        Data science is an interdisciplinary field that uses scientific methods, processes, algorithms and systems to extract knowledge and insights from structured and unstructured data.
        
        Key aspects of data science include:
        
        1. Data Collection: Gathering data from various sources, including databases, APIs, web scraping, and sensors.
        
        2. Data Cleaning: Preprocessing data to handle missing values, outliers, and inconsistencies.
        
        3. Exploratory Data Analysis (EDA): Analyzing data to discover patterns, anomalies, and relationships.
        
        4. Statistical Analysis: Applying statistical methods to validate hypotheses and make inferences.
        
        5. Machine Learning: Building predictive models using supervised and unsupervised learning techniques.
        
        6. Data Visualization: Creating visual representations of data to communicate insights effectively.
        
        Data scientists typically use programming languages like Python and R, along with specialized libraries such as Pandas, NumPy, and Scikit-learn.
        """
    },
    {
        "name": "artificial_intelligence",
        "content": """
        Artificial Intelligence (AI) is the simulation of human intelligence processes by machines, especially computer systems.
        
        Key branches of AI include:
        
        1. Machine Learning: Systems that can learn from data without being explicitly programmed.
        
        2. Natural Language Processing (NLP): Enabling computers to understand, interpret, and generate human language.
        
        3. Computer Vision: Systems that can interpret and make decisions based on visual input.
        
        4. Robotics: Physical machines that can perform tasks autonomously or semi-autonomously.
        
        5. Expert Systems: Programs designed to mimic the decision-making abilities of a human expert.
        
        AI applications are widespread, including virtual assistants, recommendation systems, autonomous vehicles, fraud detection, and medical diagnosis.
        
        Ethical considerations in AI include privacy concerns, bias in algorithms, job displacement, and the potential for autonomous weapons.
        """
    }
]

# Add texts in batch
print("Adding texts in batch...")
try:
    result = lorag.add_texts_batch(batch_texts, batch_size=2)
    file_ids = result.get("file_ids", [])
    stats = result.get("stats", {})
    
    print(f"Successfully added texts in batch with IDs: {file_ids}")
    print("\nBatch Processing Statistics:")
    print(f"Total texts: {stats.get('total', 0)}")
    print(f"Newly embedded texts: {stats.get('new_embedded', 0)}")
    print(f"Newly summarized texts: {stats.get('new_summarized', 0)}")
    print(f"Existing texts: {stats.get('existing', 0)}")
    print(f"Skipped texts: {stats.get('skipped', 0)}")
    
    # Search for content from batch-added texts
    query = "What is data science?"
    print(f"\nSearching for: '{query}'")
    results_batch = lorag.search(query, search_mode="all", n_return=1)
    
    if results_batch['results']:
        top_result = results_batch['results'][0]
        print(f"Top Result:")
        print(f"File: {top_result['file_name']}")
        print(f"Similarity: {top_result['weighted_score']:.4f}")
        print(f"Content: {top_result['content'][:200]}...")
    else:
        print("No results found.")
except Exception as e:
    print(f"Error in batch processing: {e}")
    print("Note: Batch processing requires a valid OpenAI API key with appropriate permissions.")

print("\nLORAG system demonstration completed successfully!")