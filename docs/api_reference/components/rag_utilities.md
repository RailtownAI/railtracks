# RAG Utilities

The RAG Utilities component provides essential utility functions for file operations and tokenization within the RAG system, facilitating efficient data handling and processing.

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

The RAG Utilities component is designed to support the RAG system by providing utility functions that handle file operations and tokenization. These utilities are crucial for managing data efficiently, ensuring smooth operation of the RAG system.

### 1.1 File Operations

The file operations utility functions allow for listing, reading, writing, and retrieving information about files. These operations are essential for managing data files within the RAG system.

python
# Example: Listing all .txt files in a directory
files = list_files("/path/to/directory", extensions=[".txt"])


### 1.2 Tokenization

The tokenization utilities provide functionality to encode and decode text using different tokenization models, which is vital for processing textual data in the RAG system.

python
# Example: Encoding text using the LORAGTokenizer
tokenizer = LORAGTokenizer()
tokens = tokenizer.encode("Sample text")


## 2. Public API

### `class LORAGTokenizer`
No docstring found.

#### `.__init__(self, token_encoding)`
Class constructor.

#### `.decode(self, tokens)`
Detokenize a list of tokens into text.

#### `.encode(self, text)`
Tokenize a string into a list of tokens.

#### `.count_token(self, text)`
Get the number of tokens in a string.


---
### `class Tokenizer`
No docstring found.

#### `.__init__(self, model)`
Initialize the tokenizer with a specific model.

Args:
    model: Model name (e.g., 'gpt-3.5-turbo')

#### `.encode(self, text)`
Tokenize a string into a list of tokens.

Args:
    text: Text to tokenize

Returns:
    List of token IDs

#### `.decode(self, tokens)`
Detokenize a list of tokens into text.

Args:
    tokens: List of token IDs or a single token string

Returns:
    Decoded text

#### `.count_token(self, text)`
Get the number of tokens in a string.

Args:
    text: Text to count tokens for

Returns:
    Number of tokens


---
### `def list_files(directory, extensions, recursive)`
List files in a directory.

Args:
    directory: Directory to list files from
    extensions: List of file extensions to include (e.g., ['.txt', '.md'])
    recursive: Whether to search recursively

Returns:
    List of file paths


---
### `def read_file(file_path)`
Read a file.

Args:
    file_path: Path to the file

Returns:
    File content


---
### `def write_file(file_path, content)`
Write content to a file.

Args:
    file_path: Path to the file
    content: Content to write


---
### `def get_file_info(file_path)`
Get information about a file.

Args:
    file_path: Path to the file

Returns:
    Dictionary containing file information


---

## 3. Architectural Design

### 3.1 Tokenization Classes

- **LORAGTokenizer**
  - Utilizes the `tiktoken` library to encode and decode text.
  - Supports counting tokens in a string, which is useful for understanding data size and processing needs.

- **Tokenizer**
  - Provides a model-based approach to tokenization using the `litellm` library.
  - Allows for flexible tokenization based on different models, such as "gpt-3.5-turbo".

### 3.2 File Operations

- **list_files**
  - Uses `os` and `glob` to list files in a directory, supporting recursive search and filtering by file extension.

- **read_file**
  - Reads the content of a file, ensuring the file exists before attempting to read.

- **write_file**
  - Writes content to a file, creating directories if they do not exist.

- **get_file_info**
  - Retrieves metadata about a file, such as name, size, and modification time.

## 4. Important Considerations

### 4.1 Tokenization

- The `LORAGTokenizer` and `Tokenizer` classes rely on external libraries (`tiktoken` and `litellm`), which must be installed and properly configured.

### 4.2 File Operations

- Ensure that the directory paths provided to file operations exist and are accessible to avoid runtime errors.
- The `list_files` function can be resource-intensive if used on large directories with recursive search enabled.

## 5. Related Files

### 5.1 Code Files

- [`../packages/railtracks/src/railtracks/rag/utils.py`](../packages/railtracks/src/railtracks/rag/utils.py): Contains the implementation of utility functions for file operations and tokenization.

### 5.2 Related Feature Files

- [`../features/rag_system.md`](../features/rag_system.md): Documents the RAG system, which utilizes these utility functions.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.