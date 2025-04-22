# LORAG System Design

## Overview

LORAG (Layered or Hybrid RAG) is a flexible system that combines multiple search and retrieval methods to improve the quality of generated responses by providing relevant context from external documents. The system is designed to address common limitations of traditional RAG approaches, such as irrelevant document retrieval, incomplete chunking, and over-emphasis on semantic similarity.

## System Architecture

The LORAG system is built with a modular architecture that separates concerns and allows for easy extension and customization. The main components are:

1. **Core Module**: The central component that coordinates all other modules and provides the main API.
2. **Database Module**: Manages the storage and retrieval of documents and chunks.
3. **Embedding Module**: Handles the generation and manipulation of embeddings.
4. **Text Processing Module**: Provides functionality for processing text, including chunking and summarization.
5. **Search Engine Module**: Implements different search modes and combines results from multiple search methods.
6. **Search Methods Module**: Contains individual search method implementations.
7. **Batch Processing Module**: Enables efficient batch processing of documents.

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                           LORAG Core                            │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  ┌─────────────┐   ┌────────────────┐   ┌────────────────────┐  │
│  │  Database   │   │   Embedding    │   │   Text Processing  │  │
│  │   Module    │   │     Module     │   │       Module       │  │
│  └─────────────┘   └────────────────┘   └────────────────────┘  │
│                                                                 │
│  ┌─────────────┐   ┌────────────────┐   ┌────────────────────┐  │
│  │Search Engine│   │ Search Methods │   │  Batch Processing  │  │
│  │   Module    │   │     Module     │   │       Module       │  │
│  └─────────────┘   └────────────────┘   └────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Component Details

### Core Module (`core.py`)

The Core module serves as the main entry point to the LORAG system. It initializes all other components and provides a simplified API for users to interact with the system. Key responsibilities include:

- Initializing databases and components
- Providing methods for adding files and text
- Coordinating search operations
- Managing batch processing

### Database Module (`database.py`)

The Database module handles the storage and retrieval of documents and chunks. It uses SQLite databases to store:

1. **Chunk Database**: Stores individual chunks of text with their embeddings and metadata.
2. **File Database**: Stores file-level information with global embeddings and metadata.

Key design decisions:
- Using SQLite for portability and simplicity
- Storing embeddings as binary blobs for efficiency
- Creating indexes for faster retrieval
- Separating chunk and file data for flexibility

### Embedding Module (`embedding.py`)

The Embedding module provides functionality for generating and working with embeddings. It encapsulates the interaction with the OpenAI API for embedding generation and provides utility functions for embedding manipulation. Key features include:

- Generating embeddings for text
- Calculating similarity between embeddings
- Converting embeddings to/from binary format for storage

### Text Processing Module (`text_processing.py`)

The Text Processing module handles text-related operations such as chunking and summarization. It provides:

- Text chunking with configurable size and overlap
- Text summarization using AI
- Token counting for managing context size

### Search Engine Module (`search_engine.py`)

The Search Engine module implements different search modes and combines results from multiple search methods. It supports:

- "all" mode: Execute and return results from all available search methods
- "raw" mode: Return raw data along with intermediate scores
- "smart" mode: Use AI to select the best results from each method
- "order" mode: Use search methods in a specific order, escalating if needed

### Search Methods Module (`search_methods.py`)

The Search Methods module contains implementations of various search methods, including:

1. **Embedding Search**: Standard RAG using embeddings
2. **File Name Lookup**: Search by file name
3. **File Name RAG**: Embedding-based retrieval on file names
4. **Summary RAG (Chunk)**: Search using summaries of chunks
5. **Summary RAG (Document)**: Search using summaries of entire documents
6. **Regex Search**: Search using regular expressions
7. **File Structure Traversal**: Search by traversing file structure
8. **SQL Query**: Search using SQL queries on the database
9. **Query Rewriting**: Rewrite queries to improve searchability

### Batch Processing Module (`batch.py`)

The Batch Processing module enables efficient batch processing of documents, including embedding and summarization. It leverages OpenAI's Batch API to:

- Process large numbers of documents efficiently
- Reduce costs by using batch processing
- Avoid redundant processing by checking if documents are already processed
- Handle errors and retries

## Data Flow

### Adding a Document

1. User calls `add_file()` or `add_text()`
2. The system generates a summary of the document
3. The system generates an embedding for the document
4. The document is stored in the file database
5. The document is chunked into smaller pieces
6. For each chunk:
   - Generate a summary
   - Generate an embedding
   - Store in the chunk database

### Searching for Documents

1. User calls `search()` with a query and parameters
2. Based on the search mode and effort level, the system selects search methods to use
3. Each selected search method is executed
4. Results are combined and weighted
5. If using "smart" mode, AI selects the best results
6. Results are filtered by token count if specified
7. Confidence scores are calculated
8. Final results are returned to the user

### Batch Processing

1. User calls `add_texts_batch()` with a list of texts
2. Texts are divided into batches of specified size
3. For each batch:
   - Prepare batch files for embedding and summarization
   - Upload batch files to OpenAI
   - Create batch jobs
   - Wait for batch jobs to complete
   - Download and process batch results
   - Add texts to the database

## Design Decisions

### Modularity

The system is designed with a high degree of modularity to:
- Separate concerns and reduce complexity
- Allow for easy extension and customization
- Enable independent testing of components
- Facilitate maintenance and updates

### Database Design

SQLite was chosen for the database because:
- It's portable and doesn't require a separate server
- It's simple to set up and use
- It's suitable for the expected data volume
- It supports the necessary features (indexes, binary storage)

### Search Method Selection

The system supports multiple search methods because:
- Different methods have different strengths and weaknesses
- Combining methods can provide better results than any single method
- Users have different needs and preferences
- Some methods are faster but less accurate, while others are slower but more accurate

### Batch Processing

Batch processing was implemented to:
- Reduce costs by using OpenAI's batch API
- Improve efficiency when processing large numbers of documents
- Avoid redundant processing by checking if documents are already processed
- Handle errors and retries gracefully

## Future Improvements

1. **Distributed Database**: For larger datasets, consider using a distributed database system.
2. **Vector Database**: Implement support for specialized vector databases like Pinecone or Weaviate.
3. **Local Embedding Models**: Add support for local embedding models to reduce API costs.
4. **Caching**: Implement caching for frequently accessed documents and queries.
5. **Parallel Processing**: Add support for parallel processing of documents and queries.
6. **User Interface**: Develop a web-based user interface for easier interaction.
7. **Monitoring and Logging**: Enhance monitoring and logging for better debugging and performance analysis.
8. **Security**: Implement authentication and authorization for multi-user environments.