# Text and Markdown

`TextLoader` reads `.txt` and `.md` files into [`Document`](index.md#the-document-object)
objects — one document per file. No extra dependencies.

```python
from railtracks.retrieval.loaders import TextLoader
```

---

## Loading a single file

```python
--8<-- "docs/scripts/ingestion_example.py:text_single_file"
```

Markdown files are auto-identified by the `.md` extension and get
`type="markdown"`. The chunker uses this to decide between markdown-aware
splitting (`MarkdownHeaderChunker`) and plain text splitting — set the
extension correctly and downstream stages do the right thing.

---

## Loading a directory

```python
--8<-- "docs/scripts/ingestion_example.py:text_directory"
```

Directories are walked recursively. Both `.txt` and `.md` files are picked
up. Files are returned in sorted-path order for deterministic re-ingest
behaviour.

---

## Encoding

```python
--8<-- "docs/scripts/ingestion_example.py:text_encoding"
```

`utf-8-sig` is the default — it transparently strips a BOM if present.
**Prefer `utf-8-sig` over `utf-8`** unless you know your corpus is BOM-free;
the cost is one extra check per file, the benefit is no mysterious
"weird-character-at-start-of-file" bugs.

---

## Async loading

```python
--8<-- "docs/scripts/ingestion_example.py:text_async"
```

Use `astream()` for any corpus large enough that you wouldn't want to hold
all `Document` content in memory at once. `aload()` materializes everything.

---

## Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `file_path` | `str` | — | Path to a `.txt`/`.md` file or directory |
| `encoding` | `str` | `"utf-8-sig"` | File encoding (BOM-aware by default) |

---

## Document metadata

| Key | Value |
|---|---|
| `file_type` | `".txt"` or `".md"` |
| `encoding` | The encoding used to read the file |
