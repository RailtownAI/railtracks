
# Vector Store API Reference
This page documents the core interface for embedding storage and retrieval in Railtracks. All vector store implementations follow this unified API, allowing you to swap backends without changing your code.

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
!!! tip "Vector Stores Shine When"
    - you have large collections of text
    - you need fast semantic search
    - your app uses RAG
    - you want metadata-driven filtering (where)

!!! warning "Skip Vector Stores If"
    - your whole dataset fits in one prompt
    - you're not doing retrieval
    - approximate search adds no value for your case
---

## Core Methods
#### `upsert(content: OneOrMany[Chunk] | OneOrMany[str]) -> list[str]`

```python
def upsert(self, content: OneOrMany[Chunk] | OneOrMany[str]) -> list[str]:
    """Insert or update vectors.

    Accepts either a list of `Chunk` objects or a singular `Chunk` object(preferred when you have
    metadata or an associated document id) or a list of strings or singular string.
    Returns a list of string identifiers for the inserted vectors.
    """
```

Insert new vectors or update existing ones. If an ID already exists, its data will be replaced.

Parameters:

content: Either a list of Chunk objects (with metadata) or plain strings

Returns:

List of string IDs for the inserted/updated vectors

### Example:

```python
# Simple string insertion
ids = store.upsert(["Hello world", "Another document"])

# With metadata using Chunk dataclass
from railtracks.vector_stores.vector_store_base import Chunk
chunks = Chunk(
        content="Machine learning overview",
        document="ml_guide.pdf",
        metadata={"page": 1, "author": "Jane Doe"}
        )

ids = store.upsert(chunks)
```

#### `fetch(ids: OneOrMany[str]) -> FetchResponse`

```python
def fetch(self, ids: OneOrMany[str]) -> FetchResponse:
    """Retrieve vectors by ID."""
```

Retrieve specific vectors by their IDs.

Parameters:

ids: list of vector ids to retrieve (or a singular id)

Returns:

FetchResponse containing matching FetchResult objects

### Example

```python
results = store.fetch(["vec_123", "vec_456"])
for result in results:
    print(f"{result.id}: {result.content}")
```


#### `search(query: OneOrMany[str] | OneOrMany[Chunk], top_k: int = 10, where: Optional[dict] = None, include: Optional[list[str]] = None) -> OneOrMany[SearchResponse]`

Search for vectors similar to the query text or `Chunk` content.

### Example

```python
def search(
    self,
    query: OneOrMany[str] | OneOrMany[Chunk],
    top_k: int = 10,
    where: Optional[Dict[str, Any]] = None,
    include: Optional[list[str]] = None,
) -> OneOrMany[SearchResponse]:
    """Perform semantic search."""
```

Basic usage (strings):

```python
responses = store.search("What is supervised learning?", top_k=5)
for resp in responses:  # one SearchResponse per query
    for hit in resp:
        print(hit.id, hit.distance, hit.content)
```

Using `Chunk` objects as queries (the store will use Chunk.content for embedding):

```python
from railtracks.vector_stores.vector_store_base import Chunk
q = Chunk(content="Explain gradient descent")
responses = store.search(q, top_k=3)
```

#### `delete(ids=None, where=None)`

Remove vectors.

```python
# Delete by ID (list or single id)
store.delete(ids=["vec_123", "vec_456"])

# Delete by metadata filter
store.delete(where={"document": "outdated.pdf"})

# Delete by ID with additional metadata filter
store.delete(ids=["vec_789"], where={"archived": True})
```

#### `count() -> int`

Count total vectors in the store.

```python
# Return the total number of vectors indexed in the store
total = store.count()
print(f"Total vectors: {total}")
```

---

## Data Structures

### Chunk

Chunks are used when you want explicit metadata tied to a piece of text.
```python
@dataclass
class Chunk:
    content: str
    document: Optional[str]
    metadata: Dict[str, Any]
```


### SearchResult
```python
@dataclass
class SearchResult:
    id: str
    distance: float
    content: str
    vector: List[float]
    document: Optional[str]
    metadata: Dict[str, Any]
```

### FetchResult

Same structure as SearchResult but without distances.

### SearchResponse / FetchResponse

lists of their corresponding result classes
