# Vector Store Base

The Vector Store Base defines an abstract interface for a vector store, supporting operations like adding, searching, and updating vector records. It serves as a foundational component for managing and querying vector data efficiently.

**Version:** 0.0.1

**Component Contact:** @github_username

## Table of Contents

- [1. Purpose](#1-purpose)
- [2. Public API](#2-public-api)
- [3. Architectural Design](#3-architectural-design)
- [4. Important Considerations](#4-important-considerations)
- [5. Related Files](#5-related-files)
- [CHANGELOG](#changelog)

## 1. Purpose

The Vector Store Base is designed to handle vector data operations, which are crucial for applications involving similarity search, such as recommendation systems, information retrieval, and machine learning model inference.

### 1.1 Adding Vectors

The primary use case is to add vectors or text data to the store, which can then be embedded into vectors.

python
# Example of adding vectors to the store
vector_store.add(
    texts_or_records=["sample text"],
    embed=True,
    metadata=[{"category": "example"}]
)


### 1.2 Searching Vectors

Another key use case is searching for the most similar vectors to a given query vector or text.

python
# Example of searching for similar vectors
results = vector_store.search(
    query="query text",
    top_k=5,
    embed=True
)


## 2. Public API

### `class AbstractVectorStore(abc.ABC)`
Abstract base class for a vector store interface.
Concrete implementations must provide persistent storage and similarity search.

#### `.add(self, texts_or_records)`
Add new vectors (or texts to be embedded) to the store.

Args:
    texts_or_records: A sequence of texts (if embed=True) or full VectorRecord objects.
    embed: If True, input texts will be encoded to vectors first. If False, they are expected to be VectorRecords.
    metadata: Optional sequence of metadata dicts, aligned with input texts/records (ignored if records already have metadata).

Returns:
    List of ids for the added records.

#### `.search(self, query, top_k)`
Search for the top-k most similar vectors in the store to a query string or vector.

Args:
    query: Input text (if embed=True) or vector to search against the collection.
    k: Number of top results to return.
    embed: If True, the query is assumed to be a string to embed.

Returns:
    List of search results ordered by decreasing similarity (or increasing distance).

#### `.delete(self, ids)`
Remove records from the vector store by their ID.

Args:
    ids: Sequence of ids to remove.

Returns:
    Number of records deleted.

#### `.update(self, id, new_text_or_vector, **metadata)`
Update a record, replacing its vector (or text) and/or metadata.

Args:
    id: ID of the record to update.
    new_text_or_vector: New text (if embed=True) or vector.
    embed: Whether to embed the new text input. Ignored if passing a vector.
    **metadata: Key-value pairs to update in the record's metadata.

Returns:
    None

#### `.count(self)`
Return the number of records currently stored.

#### `.persist(self, path)`
Save the store's contents to disk for later reloading.

Args:
    path: Optional filesystem path to save to. If not provided, use the store's default path.

Returns:
    None

#### `.load(cls, path)`
Rehydrate a vector store previously saved to disk.

Args:
    path: The filesystem path to load from.

Returns:
    An instance of the concrete VectorStore subclass.


---

## 3. Architectural Design

The Vector Store Base is designed with flexibility and extensibility in mind, allowing for various implementations that can handle different storage backends and similarity metrics.

### 3.1 Core Design Principles

- **Abstraction:** The use of an abstract base class (`AbstractVectorStore`) allows for different storage mechanisms to be implemented without changing the interface.
- **Metric Flexibility:** Supports multiple similarity metrics such as cosine similarity, Euclidean distance, and dot product, defined in the `Metric` enum.
- **Data Encapsulation:** Utilizes data classes (`VectorRecord` and `SearchResult`) to encapsulate vector data and search results, ensuring a consistent data structure.

## 4. Important Considerations

### 4.1 Implementation Details

- **Embedding Requirement:** When adding or searching with text, embedding is required to convert text into vectors.
- **Persistence:** Implementations must handle data persistence and reloading through the `persist` and `load` methods.

## 5. Related Files

### 5.1 Code Files

- [`base.py`](../packages/railtracks/src/railtracks/rag/vector_store/base.py): Contains the abstract base class and related data structures for vector store operations.

### 5.2 Related Feature Files

- [`rag_system.md`](../features/rag_system.md): Describes the broader RAG (Retrieval-Augmented Generation) system that utilizes the vector store.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.
