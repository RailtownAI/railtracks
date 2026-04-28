# PDFs

`PyPDFLoader` reads `.pdf` files and converts them into [`Document`](overview.md#the-document-object) objects. It requires the optional `pdf` extra:

```bash
pip install "railtracks[pdf]"
```

```python
from railtracks.retrieval.loaders.pdf_loader import PyPDFLoader
```

---

## Basic Usage

```python
loader = PyPDFLoader("report.pdf")
docs = loader.load()

# Default: one Document per page
doc = docs[0]
print(doc.content)   # extracted text from page 1
print(doc.type)      # "pdf"
print(doc.source)    # "report.pdf"
print(doc.metadata)  # {"page": 1, "total_pages": 42, "file_type": ".pdf"}
```

---

## Breakdown Strategies

`PyPDFLoader` supports two strategies for how a PDF is split into documents.

### `"page"` (default)

One `Document` per page. Each document's metadata includes the 1-based `page` number and the total page count:

```python
loader = PyPDFLoader("report.pdf", breakdown_strategy="page")
docs = loader.load()

print(len(docs))              # number of pages
print(docs[0].metadata)       # {"page": 1, "total_pages": 42, "file_type": ".pdf"}
```

!!! tip
    Page-level splitting gives the retriever finer-grained control and preserves page number metadata, making citations easier to generate.

### `"document"`

The entire PDF is returned as a single `Document`. Pages are joined with `"\n\n"`:

```python
loader = PyPDFLoader("report.pdf", breakdown_strategy="document")
docs = loader.load()

print(len(docs))        # always 1
print(docs[0].metadata) # {"total_pages": 42, "file_type": ".pdf"}
```

!!! tip
    Use the `"document"` strategy for short PDFs where you want the full context available in a single chunk, or when you plan to apply your own chunking strategy downstream.

---

## Loading a Directory

Pass a directory path to load **all** `.pdf` files recursively:

```python
loader = PyPDFLoader("contracts/", breakdown_strategy="page")
docs = loader.load()
```

---

## Async Loading

```python
loader = PyPDFLoader("report.pdf")
docs = await loader.aload()
```

---

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `file_path` | `str` | — | Path to a `.pdf` file or directory |
| `breakdown_strategy` | `"page" \| "document"` | `"page"` | How to split the PDF into Documents |

---

## Document Metadata

| Key | Strategy | Value |
|-----|----------|-------|
| `page` | `"page"` only | 1-based page number |
| `total_pages` | Both | Total number of pages in the PDF |
| `file_type` | Both | `".pdf"` |
