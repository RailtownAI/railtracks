# In-Memory Vector Store

The In-Memory Vector Store is a component designed to store and manage feature vectors and their associated metadata entirely in memory. It provides a fast and efficient way to handle vector data for applications that require quick access and manipulation of vectors, such as machine learning and data analysis tasks.

**Version:** 0.0.1

**Component Contact:** @developer_username

## Table of Contents

- [1. Purpose](#1-purpose)
- [2. Public API](#2-public-api)
- [3. Architectural Design](#3-architectural-design)
- [4. Important Considerations](#4-important-considerations)
- [5. Related Files](#5-related-files)
- [CHANGELOG](#changelog)

## 1. Purpose

The In-Memory Vector Store is primarily used for storing and managing feature vectors and their metadata in a fast and efficient manner. It is particularly useful in scenarios where quick access to vector data is crucial, such as in real-time data processing or machine learning model inference.

### 1.1 Adding Vectors

The component allows adding vectors or raw text, which can be embedded into vectors using an optional embedding service.

python
store = InMemoryVectorStore(embedding_service=my_embedding_service)
ids = store.add(["text1", "text2"], embed=True)


### 1.2 Searching Vectors

It supports searching for the most similar vectors to a given query, using various similarity metrics.

python
results = store.search("query text", top_k=3, embed=True)


## 2. Public API



## 3. Architectural Design

The In-Memory Vector Store is designed to be a lightweight and efficient solution for vector storage and retrieval. It leverages Python's built-in data structures to maintain a mapping of vector IDs to vectors and their associated metadata.

### 3.1 Core Design Principles

- **Simplicity and Efficiency:** The component is designed to be simple and efficient, using Python dictionaries to store vectors and metadata.
- **Flexibility:** Supports various similarity metrics and optional vector normalization.
- **Extensibility:** Can be extended with an embedding service to convert raw text into vectors.

## 4. Important Considerations

### 4.1 Dependencies & Setup

- **Embedding Service:** An optional embedding service can be provided to convert text into vectors. This service must implement the `BaseEmbeddingService` interface.

### 4.2 Performance & Limitations

- **Memory Usage:** As an in-memory store, it is limited by the available system memory.
- **Concurrency:** The component is not thread-safe and should be used in a single-threaded context or with external synchronization.

## 5. Related Files

### 5.1 Code Files

- [`in_memory.py`](../packages/railtracks/src/railtracks/rag/vector_store/in_memory.py): Contains the implementation of the In-Memory Vector Store.

### 5.2 Related Component Files

- [`vector_store_base.md`](../components/vector_store_base.md): Describes the base class and interfaces for vector stores.

### 5.3 Related Feature Files

- [`rag_system.md`](../features/rag_system.md): Provides an overview of the RAG system, which utilizes the vector store.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.
