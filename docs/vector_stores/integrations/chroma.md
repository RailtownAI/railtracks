# ChromaVectorStore

Railtracks' built-in implementation using ChromaDB.
```python
class ChromaVectorStore(VectorStore):
    ...
```

### Initialization and storage backends

Create a `ChromaVectorStore` by supplying a `collection_name` and an
`embedding_function`. Choose the storage backend by providing either a
filesystem `path` (for a persistent local store), a `host`/`port`
pair (for a remote HTTP-backed Chroma), or omit both to get an
ephemeral in-memory instance. Short examples for each approach are in
the Quick start examples below.

- `path`: persistent local DB (provide a filesystem path)
- `(host, port)`: remote HTTP instance (provide both values)
- omit both → ephemeral in-memory DB

---

### Quick start examples

Below are short, copy-pasteable examples that demonstrate the most
common ways to create and use a `ChromaVectorStore`. These mirror the
high-level API documented in `vector_store_info.md` and the runtime
behaviour implemented in `chroma.py`.

```python
# 1) Ephemeral (in-memory) Chroma
store = ChromaVectorStore(
        collection_name="demo_ephemeral",
        embedding_function=embed_fn,
        path=None, host=None, port=None,
)

# 2) Persistent local Chroma
store = ChromaVectorStore(
        collection_name="demo_persistent",
        embedding_function=embed_fn,
        path="/var/lib/chroma",  # example filesystem path
)

# 3) Remote HTTP Chroma
store = ChromaVectorStore(
        collection_name="demo_remote",
        embedding_function=embed_fn,
        host="chroma.example.local",
        port=8000,
)
```


### Chroma-specific behaviour

This section briefly documents what `ChromaVectorStore` adds on top of
the generic vector-store API (the general semantics live in
`vector_store_info.md`).

- Initialization: `ChromaVectorStore.class_init` chooses between a
        persistent, HTTP or ephemeral client based on `path` or `(host, port)`.
        Provide a filesystem `path` (persistent) or both `host` and `port`
        (HTTP). Passing an invalid/mixed combination raises `ValueError`.

- fetch extras: `fetch(ids=None, where=None, where_document=None)`
        - `where/where_document` : Allows for metadata filtering and document filtering
        - `limit` : Allows the user to specify a limit to number of return documents

- search differences: `search(query, ids=None, top_k=10, where=None, where_document=None, include=...)`
        - `where_document` : Allows the user to filter by document as well
        - `include` : Allows user to choose what is returned for SearchResults. It defaults to `['metadatas','embeddings','documents','distances']`.

- delete: accepts `ids` (single or list) and `where`/`where_document` to
        - `where_document` : Allows the user to filter by document as well



