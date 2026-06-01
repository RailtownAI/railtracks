# PDFs

Two PDF loaders ship with Railtracks. **Pick `PyPDFLoader` when your PDFs
have a text layer; pick `PyPDFOCRLoader` when some pages are scanned
images.** The OCR loader has a slower fast-path but handles mixed corpora
transparently.

---

## `PyPDFLoader`

For PDFs with embedded text. Skips pages that have no text layer
(scanned-image pages return empty).

```bash
pip install "railtracks[pdf]"
```

```python
from railtracks.retrieval.loaders.pdf_loader import PyPDFLoader
```

### Basic usage

```python
--8<-- "docs/scripts/ingestion_example.py:pdf_basic"
```

### Breakdown strategies

One PDF can produce either many Documents (one per page) or a single
Document containing the whole text.

**`"page"` (default) — one Document per page**

```python
--8<-- "docs/scripts/ingestion_example.py:pdf_page_strategy"
```

Use the page strategy for retrieval. It keeps page numbers in metadata,
which makes citations trivial and lets the chunker make sane decisions per
page rather than across a 200-page document.

**`"document"` — one Document for the whole PDF**

```python
--8<-- "docs/scripts/ingestion_example.py:pdf_document_strategy"
```

Use this only when the PDF is small enough to chunk as a single unit or
you want to apply custom splitting that crosses page boundaries.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `file_path` | `str` | — | Path to a `.pdf` file or directory |
| `breakdown_strategy` | `"page" \| "document"` | `"page"` | How to split the PDF into Documents |

### Document metadata

| Key | Strategy | Value |
|---|---|---|
| `page` | `"page"` only | 1-based page number |
| `total_pages` | Both | Total number of pages in the PDF |
| `file_type` | Both | `".pdf"` |

---

## `PyPDFOCRLoader` (scanned PDFs)

`PyPDFLoader` reads embedded text only. For PDFs that contain scanned
pages (or a mix), `PyPDFOCRLoader` falls back to OCR via Tesseract on any
page where text extraction returns nothing.

### Installation

OCR needs both Python packages and a system binary.

**Python packages** (via the `ocr` extra — pulls in `pypdfium2`,
`pytesseract`, `pillow`, `pypdf`):

```bash
pip install "railtracks[ocr]"
```

**Tesseract** is a separate OS-level binary; pip cannot install it. Follow
the official instructions: [tesseract-ocr.github.io/tessdoc/Installation.html](https://tesseract-ocr.github.io/tessdoc/Installation.html).

Verify in a fresh terminal:

```bash
tesseract --version
```

```python
from railtracks.retrieval.loaders.pdf_ocr_loader import PyPDFOCRLoader
```

### Basic usage

```python
--8<-- "docs/scripts/ingestion_example.py:pdf_ocr_basic"
```

For each page, the loader tries pypdf text extraction first (fast, no OCR
cost). If that returns empty, it rasterizes the page at 300 DPI with
`pypdfium2` and OCRs the image with Tesseract. **Mixed PDFs work
transparently** — each page picks its own path.

### Forcing OCR on every page

```python
--8<-- "docs/scripts/ingestion_example.py:pdf_ocr_force"
```

Some PDFs have a garbled or incomplete text layer that pypdf will happily
return. `force_ocr=True` skips the fast path and re-OCRs unconditionally.

### Document strategy returns OCR provenance

```python
--8<-- "docs/scripts/ingestion_example.py:pdf_ocr_document_strategy"
```

`ocr_pages` is the sorted list of 1-based page numbers that required OCR
— useful for auditing how much of a corpus needed image-based extraction.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `file_path` | `str` | — | Path to a `.pdf` file or directory |
| `breakdown_strategy` | `"page" \| "document"` | `"page"` | How to split the PDF into Documents |
| `force_ocr` | `bool` | `False` | OCR every page, skipping the text-extraction fast path |
| `dpi` | `int` | `300` | OCR rendering resolution. 300 is Tesseract's sweet spot; higher trades speed/memory for accuracy. |
| `language` | `str` | `"eng"` | Tesseract language code (e.g. `"eng"`, `"eng+deu"`, `"jpn"`) |

### Document metadata

| Key | Strategy | Value |
|---|---|---|
| `page` | `"page"` only | 1-based page number |
| `total_pages` | Both | Total number of pages in the PDF |
| `file_type` | Both | `".pdf"` |
| `ocr` | `"page"` only | `True` if OCR was used for this page, `False` if pypdf returned text |
| `ocr_pages` | `"document"` only | Sorted list of 1-based page numbers that required OCR |

!!! tip "Tesseract limitations"
    Tesseract is the default OCR engine because it's permissively licensed
    and runs locally. For handwriting, low-quality scans, or formatted
    layouts (tables, forms), accuracy will be poor — that's Tesseract, not
    the loader. The [`BaseOCRLoader`](https://github.com/RailtownAI/railtracks/blob/main/packages/railtracks/src/railtracks/retrieval/loaders/base_ocr.py)
    abstraction lets future loaders plug in cloud OCR or LLM-vision engines
    by overriding `_ocr_image`.
