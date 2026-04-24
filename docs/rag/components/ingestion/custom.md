# Custom Ingestors

When the built-in loaders don't cover your source, you can write your own by subclassing `BaseDocumentLoader`, or bridge any LangChain-compatible loader with `LangChainLoaderAdapter`.

---

## Writing a Custom Loader

Subclass `BaseDocumentLoader` and implement `load()`. Async support comes for free — `aload()` runs `load()` in a thread pool by default, and you can override it if your source supports native async I/O.

```python
from railtracks.retrieval.loaders import BaseDocumentLoader
from railtracks.retrieval.models import Document


class MyDatabaseLoader(BaseDocumentLoader):
    """Loads rows from a database table as Documents."""

    def __init__(self, connection_string: str, table: str) -> None:
        self._connection_string = connection_string
        self._table = table

    def load(self) -> list[Document]:
        # Replace with your actual database logic
        rows = fetch_rows(self._connection_string, self._table)
        return [
            Document(
                content=row["body"],
                type="database",
                source=f"{self._table}:{row['id']}",
                metadata={"author": row["author"], "created_at": row["created_at"]},
            )
            for row in rows
        ]
```

Then use it like any other loader:

```python
loader = MyDatabaseLoader("postgresql://...", table="articles")
docs = loader.load()
```

### Overriding `aload()` for True Async I/O

If your source has a native async API, override `aload()` directly:

```python
class MyAsyncLoader(BaseDocumentLoader):
    async def aload(self) -> list[Document]:
        rows = await async_fetch_rows(...)
        return [Document(content=r["text"], type="custom", ...) for r in rows]

    def load(self) -> list[Document]:
        import asyncio
        return asyncio.run(self.aload())
```

---

## LangChain Loader Adapter

`LangChainLoaderAdapter` wraps any LangChain-compatible loader and converts its output to Railtracks `Document` objects. `langchain-core` is **not** a required dependency — any object whose `.load()` returns items with `.page_content` and `.metadata` attributes is accepted.

```python
from langchain_community.document_loaders import NotionDirectoryLoader
from railtracks.retrieval.loaders import LangChainLoaderAdapter

docs = LangChainLoaderAdapter(
    NotionDirectoryLoader("notion_export/")
).load()
```

`aload()` calls the wrapped loader's own `.aload()` if it exists, otherwise falls back to the thread-pool default.

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
| `content_keys` | `list[str] \| None` | `None` | Keys whose values form `Document.content`. `None` serializes the whole object. |
| `ignore_keys` | `list[str] \| None` | `None` | Keys to drop entirely |
| `content_separator` | `str` | `"\n"` | Separator used to join content-key values |
| `encoding` | `str` | `"utf-8-sig"` | File encoding |

---

### HTML

`HTMLLoader` loads an HTML file or URL, strips tags, and returns a single `Document` with the plain text. Requires the optional `html` extra:

```bash
pip install "railtracks[html]"
```

```python
from railtracks.retrieval.loaders.html_loader import HTMLLoader

# From a URL
loader = HTMLLoader("https://example.com/page")
docs = loader.load()

# From a local file, extracting only article content
loader = HTMLLoader("page.html", tags_to_extract=["article", "main"])
docs = loader.load()
```

Metadata includes `title` (from `<title>`), `source`, and any `<meta>` tags with both `name` and `content` attributes.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source` | `str` | — | File path or HTTP/HTTPS URL |
| `tags_to_extract` | `list[str] \| None` | `None` | HTML tags to extract text from. `None` extracts the full body. |
| `encoding` | `str` | `"utf-8"` | Encoding for local files |

---

### Code

`CodeLoader` loads a single source-code file as one `Document` and detects the programming language from the file extension.

```python
from railtracks.retrieval.loaders import CodeLoader

loader = CodeLoader("src/utils.py")
docs = loader.load()

doc = docs[0]
print(doc.metadata["language"])   # "python"
print(doc.metadata["extension"])  # ".py"
```

Supported languages: Python, TypeScript, JavaScript, Go, Rust, Java, C++, C, C#, Ruby, PHP, Swift, Kotlin, Bash, SQL, HTML, CSS, YAML, JSON, TOML. Unknown extensions default to `"text"`.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `file_path` | `str` | — | Path to the source file |
| `encoding` | `str` | `"utf-8"` | File encoding |
