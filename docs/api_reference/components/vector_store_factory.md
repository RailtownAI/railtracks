# Vector Store Factory

The Vector Store Factory provides a utility function to create a vector store based on a given configuration. It abstracts the complexity of initializing different types of vector stores, allowing users to specify their preferences through a configuration dictionary.

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

The primary purpose of the Vector Store Factory is to provide a flexible and extensible way to create vector stores. This is particularly useful in applications that require efficient storage and retrieval of high-dimensional vectors, such as machine learning models and recommendation systems.

### 1.1 Creating an In-Memory Vector Store

The factory can be used to create an in-memory vector store, which is useful for applications that require fast access to vectors without the overhead of persistent storage.

python
from railtracks.rag.vector_store.factory import create_store

config = {
    "backend": "memory",
    "metric": "cosine",
    "workspace": "~/.vector_store",
    "dim": 768
}

vector_store = create_store(config)


## 2. Public API

### `def create_store(cfg)`
Factory utility.
Example cfg:
    {
        "backend": "memory"
        "metric": "cosine",
        "workspace": "~/.vector_store",
        "dim": 768
    }


---

## 3. Architectural Design

The Vector Store Factory is designed to be extensible and easy to use. It currently supports the creation of in-memory vector stores, with the potential to add more backends in the future.

### 3.1 Design Considerations

- **Extensibility:** The factory pattern allows for easy addition of new vector store backends. Developers can extend the factory to support new types of vector stores by adding new conditions in the `create_store` function.
- **Simplicity:** The use of a configuration dictionary makes it easy to specify the desired properties of the vector store without needing to understand the underlying implementation details.

## 4. Important Considerations

### 4.1 Configuration Details

- The `cfg` parameter is a dictionary that specifies the configuration for the vector store. It must include a `backend` key, which determines the type of vector store to create.
- The `embedding_service` parameter is optional and can be used to specify a custom embedding service for the vector store.

### 4.2 Error Handling

- If an unknown backend is specified in the configuration, the factory will raise a `ValueError`. This ensures that only supported backends are used.

## 5. Related Files

### 5.1 Code Files

- [`../in_memory.py`](../in_memory.py): Contains the implementation of the `InMemoryVectorStore` class, which is used when the `memory` backend is specified.

### 5.2 Related Component Files

- [`../components/vector_store_base.md`](../components/vector_store_base.md): Provides the base interface and common functionality for all vector store implementations.

### 5.3 Related Feature Files

- [`../features/rag_system.md`](../features/rag_system.md): Describes the RAG (Retrieval-Augmented Generation) system, which utilizes vector stores for efficient data retrieval.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.

