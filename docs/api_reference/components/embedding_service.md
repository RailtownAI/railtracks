# Embedding Service

The Embedding Service is designed to generate embeddings for text data using the `litellm` library. It provides a convenient interface for embedding tasks, primarily focusing on text processing within the larger project.

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

The Embedding Service is used to convert text data into numerical embeddings, which are essential for various natural language processing tasks such as similarity search, clustering, and classification.

### 1.1 Text Embedding

The primary use case of the Embedding Service is to generate embeddings for a batch of text inputs. This is crucial for applications that require text data to be represented in a numerical format for further processing or analysis.

python
from railtracks.rag.embedding_service import EmbeddingService

# Initialize the embedding service
embedding_service = EmbeddingService()

# Example texts to embed
texts = ["Hello world", "Embedding service example"]

# Generate embeddings
embeddings = embedding_service.embed(texts)
print(embeddings)


## 2. Public API

### `class EmbeddingService(BaseEmbeddingService)`
Embedding service that uses litellm to perform embedding tasks.

#### `.__init__(self, model, **litellm_extra)`
Initialize the embedding service.

Args:
    model: Model name (OpenAI, TogetherAI, etc.)
    api_key: If None, taken from OPENAI_API_KEY env var.
    base_url: Override OpenAI base URL if using gateway / proxy.
    timeout: Per-request timeout in seconds.
    **litellm_extra: Any other args passed straight to litellm.embedding
                    (e.g. headers, organization, etc.)

#### `.embed(self, texts)`
Convenience wrapper to embed many short texts in one go.


---

## 3. Architectural Design

The Embedding Service is built around the `litellm` library, which provides the core functionality for generating embeddings. The service is designed to be flexible and configurable, allowing users to specify different models and parameters.

### 3.1 Design Considerations

- **Model Selection:** The service uses a default model (`text-embedding-3-small`) but allows customization through the constructor.
- **Batch Processing:** Texts are processed in batches to optimize performance and manage resource usage effectively.
- **Extensibility:** The service is designed to be extended for different embedding models and configurations.

## 4. Important Considerations

### 4.1 Configuration and Dependencies

- **API Key:** The service requires an API key for authentication, which can be provided directly or through the `OPENAI_API_KEY` environment variable.
- **Timeouts:** The service includes a configurable timeout for requests to prevent long-running operations from blocking the system.

### 4.2 Performance

- **Batch Size:** The batch size can be adjusted to balance between performance and resource consumption. Larger batch sizes may improve throughput but require more memory.

## 5. Related Files

### 5.1 Code Files

- [`embedding_service.py`](../packages/railtracks/src/railtracks/rag/embedding_service.py): Contains the implementation of the Embedding Service.

### 5.2 Related Feature Files

- [`rag_system.md`](../docs/features/rag_system.md): Provides an overview of the RAG system, which utilizes the Embedding Service for text processing tasks.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.
