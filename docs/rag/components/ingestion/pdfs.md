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

---

# Scanned PDFs (`PyPDFOCRLoader`)

`PyPDFLoader` reads embedded text only — it skips pages with no text layer (e.g. scanned documents stored as images). `PyPDFOCRLoader` handles both text-based and scanned PDFs in a single loader by falling back to OCR (Tesseract via `pytesseract`) on pages where text extraction returns nothing.

## Installation

OCR requires both Python packages and a system binary.

**1. Install the Python packages** via the `ocr` extra:

```bash
pip install "railtracks[ocr]"
```

This pulls in `pypdfium2` (for page rasterization), `pytesseract`, `pillow`, and `pypdf`.

**2. Install Tesseract on your system** and make sure it is on `PATH`. Tesseract is a separate OS-level binary — pip cannot install it.

Follow the official install instructions: [https://tesseract-ocr.github.io/tessdoc/Installation.html](https://tesseract-ocr.github.io/tessdoc/Installation.html).

Verify it works in a fresh terminal:

```bash
tesseract --version
```

```python
from railtracks.retrieval.loaders.pdf_ocr_loader import PyPDFOCRLoader
```

---

## Basic Usage

```python
loader = PyPDFOCRLoader("scanned_invoice.pdf")
docs = loader.load()

doc = docs[0]
print(doc.content)        # OCR'd text from page 1
print(doc.metadata["ocr"]) # True if this page required OCR, False if pypdf got text
```

For each page, the loader:

1. Tries `pypdf` text extraction first (fast, no OCR cost).
2. If that returns empty/whitespace, rasterizes the page with `pypdfium2` at 300 DPI and OCRs the image with Tesseract.

This means **mixed PDFs** (some pages typed, some scanned) work transparently — each page uses whichever path is appropriate.

---

## Forcing OCR on Every Page

Some PDFs have a garbled or incomplete text layer that pypdf will happily return. Pass `force_ocr=True` to skip the text-extraction fast path and OCR every page unconditionally:

```python
loader = PyPDFOCRLoader("messy_scan.pdf", force_ocr=True)
docs = loader.load()

assert all(d.metadata["ocr"] for d in docs)
```

---

## Breakdown Strategies

Same `"page"` / `"document"` strategies as `PyPDFLoader`, with one extra field per Document recording whether OCR was used.

### `"page"` (default)

```python
loader = PyPDFOCRLoader("report.pdf", breakdown_strategy="page")
docs = loader.load()

print(docs[0].metadata)
# {"page": 1, "total_pages": 42, "file_type": ".pdf", "ocr": False}
```

Empty pages (where both text extraction and OCR return nothing) are skipped.

### `"document"`

```python
loader = PyPDFOCRLoader("report.pdf", breakdown_strategy="document")
docs = loader.load()

print(docs[0].metadata)
# {"total_pages": 42, "file_type": ".pdf", "ocr_pages": [3, 7, 8]}
```

`ocr_pages` is a sorted list of 1-based page numbers that required OCR — useful for auditing how much of a corpus was scanned.

---

## Loading a Directory

```python
loader = PyPDFOCRLoader("contracts/")
docs = loader.load()
```

---

## Async Loading

```python
loader = PyPDFOCRLoader("report.pdf")
docs = await loader.aload()
```

OCR is CPU-bound and runs in a worker thread, so the async pipeline keeps streaming pages without blocking the event loop.

---

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `file_path` | `str` | — | Path to a `.pdf` file or directory |
| `breakdown_strategy` | `"page" \| "document"` | `"page"` | How to split the PDF into Documents |
| `force_ocr` | `bool` | `False` | OCR every page, skipping the text-extraction fast path |
| `dpi` | `int` | `300` | Rendering resolution for OCR. 300 is the standard Tesseract sweet spot; higher improves accuracy at the cost of speed/memory |
| `language` | `str` | `"eng"` | Tesseract language code (e.g. `"eng"`, `"eng+deu"`, `"jpn"`) |

---

## Document Metadata

| Key | Strategy | Value |
|-----|----------|-------|
| `page` | `"page"` only | 1-based page number |
| `total_pages` | Both | Total number of pages in the PDF |
| `file_type` | Both | `".pdf"` |
| `ocr` | `"page"` only | `True` if OCR was used for this page, `False` if pypdf returned text |
| `ocr_pages` | `"document"` only | Sorted list of 1-based page numbers that required OCR |

!!! tip
    Tesseract is the default OCR engine because it ships under a permissive license and runs locally. For handwriting, low-quality scans, or formatted layouts (tables, forms), accuracy will be poor — that's a limitation of Tesseract, not the loader. The [`BaseOCRLoader`](https://github.com/RailtownAI/railtracks/blob/main/packages/railtracks/src/railtracks/retrieval/loaders/base_ocr.py) abstraction lets future loaders plug in alternative engines (cloud OCR, LLM vision, etc.) by overriding `_ocr_image`.
