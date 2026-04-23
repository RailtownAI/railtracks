# Text and Markdown

`TextLoader` reads `.txt` and `.md` files and converts each file into a single [`Document`](overview.md#the-document-object). No extra dependencies are required.

```python
from railtracks.retrieval.loaders import TextLoader
```

---

## Loading a Single File

```python
loader = TextLoader("notes.txt")
docs = loader.load()  # returns [Document]

doc = docs[0]
print(doc.content)            # full file text
print(doc.type)               # "text" or "markdown"
print(doc.source)             # "notes.txt"
print(doc.metadata)           # {"file_type": ".txt", "encoding": "utf-8"}
```

Markdown files are automatically identified by their `.md` extension and get `type="markdown"`:

```python
loader = TextLoader("README.md")
docs = loader.load()
print(docs[0].type)  # "markdown"
```

---

## Loading a Directory

Pass a directory path and `TextLoader` will recursively find **all** `.txt` and `.md` files:

```python
loader = TextLoader("knowledge_base/")
docs = loader.load()

print(len(docs))         # one Document per file
print(docs[0].source)    # full path to the file
```

Files are returned in sorted order by path.

---

## Encoding

The default encoding is `utf-8`. Override it with the `encoding` argument:

```python
loader = TextLoader("legacy_docs/", encoding="latin-1")
docs = loader.load()
```

The encoding used is stored in each document's metadata:

```python
doc.metadata["encoding"]  # "latin-1"
```

---

## Async Loading

```python
loader = TextLoader("docs/")
docs = await loader.aload()
```

---

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `file_path` | `str` | — | Path to a `.txt`/`.md` file or a directory |
| `encoding` | `str` | `"utf-8"` | File encoding |

---

## Document Metadata

| Key | Value |
|-----|-------|
| `file_type` | `".txt"` or `".md"` |
| `encoding` | The encoding used to read the file |
