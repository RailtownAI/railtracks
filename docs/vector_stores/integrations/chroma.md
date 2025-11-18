# ChromaVectorStore

### Quick start examples

Below are short, copy-pasteable examples that demonstrate the most
common ways to create and use a `ChromaVectorStore`.


```python
--8<-- "docs/scripts/chroma.py:first_chroma_example"
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



