# RAG Core

The RAG Core component implements a Retrieval-Augmented Generation (RAG) system for document processing, embedding, and search. It is designed to efficiently handle large volumes of text data by chunking, embedding, and storing them for quick retrieval and similarity search.

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

The RAG Core component is primarily used for processing and managing large text datasets. It allows for efficient text chunking, embedding, and storage, enabling fast and accurate similarity searches. This is particularly useful in applications such as document retrieval, question answering, and content recommendation systems.

### 1.1 Text Chunking and Embedding

The component processes raw text by dividing it into manageable chunks and generating embeddings for each chunk. This is crucial for handling large documents and ensuring that the embeddings are accurate and relevant.

python
from rag_core import RAG

# Initialize RAG with text documents
rag = RAG(docs=["This is a sample document."], input_type="text")

# Embed all documents
rag.embed_all()


### 1.2 Similarity Search

Once the text is processed and stored, the component allows for efficient similarity searches, returning the most relevant documents or text chunks based on a query.

python
# Perform a search with a query
results = rag.search(query="sample query", top_k=3)
for result in results:
    print(result.record.text)


## 2. Public API



## 3. Architectural Design

The RAG Core component is designed with modularity and scalability in mind. It integrates several sub-components to achieve its functionality:

- **TextChunkingService**: Responsible for dividing text into chunks. It supports multiple strategies, such as chunking by character or token. [See `chunking_service.py`](../packages/railtracks/src/railtracks/rag/chunking_service.py)
- **EmbeddingService**: Utilizes the `litellm` library to generate embeddings for text chunks. [See `embedding_service.py`](../packages/railtracks/src/railtracks/rag/embedding_service.py)
- **VectorStore**: Manages the storage and retrieval of vector embeddings. It supports CRUD operations and similarity searches. [See `vector_store/base.py`](../packages/railtracks/src/railtracks/rag/vector_store/base.py)

### 3.1 Design Considerations

- **Modularity**: Each service (chunking, embedding, storage) is encapsulated in its own class, allowing for easy replacement or extension.
- **Scalability**: The system is designed to handle large datasets by processing text in chunks and storing embeddings efficiently.
- **Flexibility**: Supports different chunking strategies and embedding models, making it adaptable to various use cases.

## 4. Important Considerations

### 4.1 Dependencies & Setup

- **Environment Variables**: The `EmbeddingService` may require an API key for `litellm`, which can be set via the `OPENAI_API_KEY` environment variable.
- **Configuration**: The component accepts configuration dictionaries for embedding, storage, and chunking services, allowing for customization.

### 4.2 Performance & Limitations

- **Chunk Size**: The performance of the chunking process can be affected by the chosen chunk size and overlap. It is recommended to keep the overlap less than or equal to 40% of the chunk size.
- **Embedding Model**: The choice of embedding model impacts both the quality of embeddings and the computational resources required.

## 5. Related Files

### 5.1 Code Files

- [`chunking_service.py`](../packages/railtracks/src/railtracks/rag/chunking_service.py): Handles text chunking operations.
- [`embedding_service.py`](../packages/railtracks/src/railtracks/rag/embedding_service.py): Manages text embedding using `litellm`.
- [`text_object.py`](../packages/railtracks/src/railtracks/rag/text_object.py): Defines the `TextObject` class for managing text metadata and embeddings.
- [`vector_store/base.py`](../packages/railtracks/src/railtracks/rag/vector_store/base.py): Provides the base class for vector storage and retrieval.

### 5.2 Related Component Files

- [`chunking_service.md`](components/chunking_service.md): Documentation for the chunking service component.
- [`embedding_service.md`](components/embedding_service.md): Documentation for the embedding service component.

### 5.3 Related Feature Files

- [`rag_system.md`](features/rag_system.md): Documentation for the RAG system feature.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.
