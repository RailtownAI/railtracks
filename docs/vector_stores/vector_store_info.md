
# Vector Store Implementation

## When to Use Vector Stores
!!! tip "Vector Stores Shine When"
    - You have large collections of text that won't fit in a single prompt
    - You need fast semantic search across documents
    - Your application uses RAG (Retrieval Augmented Generation)
    - You want metadata-driven filtering for targeted queries
    - You're building a knowledge base or document search system
!!! warning "Skip Vector Stores If"
    - Your entire dataset fits comfortably in one prompt (< 100K tokens)
    - You're not doing similarity search or retrieval
    - Your use case requires exact matching (use a traditional database)
    - Approximate nearest neighbor search adds no value


## Core Methods
|Methods|Description|
|-------|-----------|
|`upsert()`|Insert new vectors or update existing ones|
|`fetch()`|Retrieve specific vectors by their IDs|
|`search()`|Search for vectors similar to the query|
|`delete()`|Remove vectors|
|`count()`|Count total vectors in the store|