# Custom Ingestors

When the built-in loaders don't cover your source, you can write your own by subclassing `BaseDocumentLoader`.
---

## Writing a Custom Loader

Subclass `BaseDocumentLoader` and implement `astream()`. It must be an async generator that yields `Document` objects one at a time. `aload()` and `load()` come for free — they both derive from `astream()`.

```python
from collections.abc import AsyncGenerator

from railtracks.retrieval.loaders import BaseDocumentLoader
from railtracks.retrieval.models import Document, DocumentType


class MyDatabaseLoader(BaseDocumentLoader):
    """Loads rows from a database table as Documents."""

    def __init__(self, connection_string: str, table: str) -> None:
        self._connection_string = connection_string
        self._table = table

    async def astream(self) -> AsyncGenerator[Document, None]:
        rows = await async_fetch_rows(self._connection_string, self._table)
        for row in rows:
            yield Document(
                content=row["body"],
                type=DocumentType.TEXT,
                source=f"{self._table}:{row['id']}",
                metadata={"author": row["author"], "created_at": row["created_at"]},
            )
```

Then use it like any other loader:

```python
loader = MyDatabaseLoader("postgresql://...", table="articles")
docs = loader.load()                   # sync
docs = await loader.aload()            # async, all at once
async for doc in loader.astream():     # async, one at a time
    ...
```

### Wrapping a Sync Source

If your source only has a synchronous API, use `asyncio.to_thread()` to avoid blocking the event loop:

```python
import asyncio
from collections.abc import AsyncGenerator

class MySyncLoader(BaseDocumentLoader):
    async def astream(self) -> AsyncGenerator[Document, None]:
        rows = await asyncio.to_thread(fetch_rows_sync, ...)
        for row in rows:
            yield Document(content=row["text"], type=DocumentType.TEXT, ...)
```

---

## Other Built-in Loaders

### JSON

`JSONLoader` reads `.json` files where the root is an object or an array of objects. Each object becomes one `Document`. Works the same as `CSVLoader` — use `content_keys` to select which keys form the document content, and `ignore_keys` to drop keys entirely.

```python
from railtracks.retrieval.loaders.json_loader import JSONLoader

loader = JSONLoader(
    "articles.json",
    content_keys=["title", "body"],
    ignore_keys=["internal_id"],
)
docs = loader.load()

doc = docs[0]
print(doc.content)   # "title: Getting started\nbody: ..."
print(doc.metadata)  # {"author": "Alice", "index": 0}
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `file_path` | `str` | — | Path to a `.json` file or directory |
| `content_keys` | `list[str] \| "*"` | `"*"` | Keys whose values form `Document.content`. `"*"` serialises the whole object as JSON. |
| `ignore_keys` | `list[str] \| None` | `None` | Keys to drop entirely |
| `content_separator` | `str` | `"\n"` | Separator used to join content-key values |
| `encoding` | `str` | `"utf-8-sig"` | File encoding |

---