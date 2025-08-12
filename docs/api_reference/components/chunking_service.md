# Chunking Service

The Chunking Service is a component designed to process text by dividing it into manageable chunks. It supports various chunking strategies, including character-based and token-based chunking, and is intended to facilitate text processing tasks such as summarization and analysis.

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

The Chunking Service is primarily used to divide large text bodies into smaller, more manageable pieces. This is particularly useful in scenarios where text needs to be processed in parts, such as in natural language processing tasks or when dealing with large documents that exceed processing limits.

### 1.1 Character-Based Chunking

Character-based chunking splits text into chunks of a specified number of characters, allowing for overlap between chunks to ensure continuity.

python
chunker = TextChunkingService(chunk_size=1000, chunk_overlap=100)
chunks = chunker.chunk_by_char("This is a long text that needs to be chunked...")


### 1.2 Token-Based Chunking

Token-based chunking divides text into chunks based on tokens, which are typically words or subwords, using a specified model for tokenization.

python
chunker = TextChunkingService(chunk_size=100, chunk_overlap=10, model="gpt-3.5-turbo")
chunks = chunker.chunk_by_token("This is a long text that needs to be chunked...")


## 2. Public API

### `class BaseChunkingService`
Base class for media chunking services.

Args:
    chunk_size (int): Size of each chunk in bytes/tokens/characters.
    chunk_overlap (int): Overlap between chunks.
    strategy (Optional[Callable]): Callable for the chunking strategy.

#### `.__init__(self, chunk_size, chunk_overlap, strategy, *other_configs, **other_kwargs)`
Class constructor.

#### `.chunk(self, content, *args, **kwargs)`
Invoke the assigned chunking strategy on content.

Args:
    content: The media/text to chunk.
    *args, **kwargs: Passed to the chunking strategy.
Returns:
    Chunked content as per the strategy.

#### `.set_strategy(self, new_strategy)`
Set a new chunking strategy, binding it if needed.

#### `.chunk_file(self, file_path)`
Split file into chunks based on strategy.


---
### `class TextChunkingService(BaseChunkingService)`
Processor for text operations.

#### `.__init__(self, chunk_size, chunk_overlap, model, strategy, *other_configs, **other_kwargs)`
Initialize the text chunker.

Args:
    chunk_size: Size of each chunk in characters
    chunk_overlap: Overlap between chunks in characters

#### `.chunk_by_char(self, content)`
Split text into chunks

#### `.chunk_by_token(self, content)`
Split text into chunks by token.

TODO: use LLM to do this

#### `.chunk_smart(self, content)`
Smart chunking using LLM to determine optimal chunk size.

Args:
    content: Text content to be chunked
    model: Model to use for smart chunking

Returns:
    List of text chunks


---

## 3. Architectural Design

### 3.1 Design Principles

- **Modularity:** The service is designed to be modular, allowing different chunking strategies to be implemented and swapped easily.
- **Extensibility:** New chunking strategies can be added by subclassing `BaseChunkingService` and implementing the `chunk_file` method.
- **Flexibility:** The service supports both character-based and token-based chunking, with the potential for more sophisticated strategies like smart chunking.

### 3.2 Data Flow

- **Input:** Text content is provided to the service, either as a string or a file path.
- **Processing:** The content is processed using the specified chunking strategy, which divides it into chunks.
- **Output:** The resulting chunks are returned as a list of strings.

## 4. Important Considerations

### 4.1 Dependencies & Setup

- **Tokenizer:** The `TextChunkingService` relies on a `Tokenizer` class for token-based chunking. Ensure that the appropriate model is specified and available.
- **Logging:** The service uses Python's logging module to report errors and warnings.

### 4.2 Performance & Limitations

- **Chunk Overlap:** Ensure that `chunk_overlap` is less than or equal to `chunk_size` to avoid errors.
- **Model Dependency:** Token-based chunking requires a specified model for tokenization. If no model is provided, an error will be raised.

## 5. Related Files

### 5.1 Code Files

- [`chunking_service.py`](../packages/railtracks/src/railtracks/rag/chunking_service.py): Contains the implementation of the Chunking Service.

### 5.2 Related Component Files

- [Tokenizer Documentation](../docs/api_reference/index.md): Provides details on the `Tokenizer` class used for token-based chunking.

## CHANGELOG

- **v0.0.1** (2023-10-01) [`<COMMIT_HASH>`]: Initial version.

