# Module Packages

The retrieval stack is split across optional extras so you don't pay
the dependency cost of connectors you don't use. Pick the smallest
set that covers what you're building.

---

## Pick by use case

| You want to… | Install |
|---|---|
| Try retrieval end-to-end with everything available | `pip install "railtracks[retrieval]"` |
| Build a retrieval pipeline against your own loader/store | `pip install "railtracks[retrieval-core]"` |
| Add a specific source (S3, GCS, Azure Blob, SQL, HuggingFace) | `[retrieval-core]` + the connector extra |
| OCR scanned PDFs | `[retrieval-core]` + `[ocr]` (plus the Tesseract system binary) |
| Use a real vector store backend | `[retrieval-core]` + `[stores-vector]` or `[stores-chroma]` |

---

## Extras

### **`[retrieval-core]`** 

The minimum to run the pipeline. Includes
chunking (`tiktoken`), the basic PDF loader (`pypdf`), and the
`InMemoryBackend` (`numpy`). Use this when you're wiring your own
loader or store and don't want the full integration set.

```bash
pip install "railtracks[retrieval-core]"
```

### **`[retrieval]`**:

`[retrieval-core]` plus every built-in connector
and backend (OCR, HuggingFace, ChromaDB, AWS, Azure Blob, GCP, SQL,
pgvector). Largest install; use when you want everything available.

```bash
pip install "railtracks[retrieval]"
```

---

## Granular extras

Combine these with `[retrieval-core]` to add specific capabilities.

| Extra | Adds | For |
|---|---|---|
| `[ocr]` | `pypdfium2`, `pytesseract`, `pillow` | OCR fallback in `PyPDFOCRLoader`. Also needs the [Tesseract binary](https://tesseract-ocr.github.io/tessdoc/Installation.html) on `PATH`. |
| `[huggingface]` | `datasets` | `HuggingFaceDatasetLoader` for streaming HF datasets. |
| `[chroma]` | `chromadb`, `pdfplumber` | ChromaDB-backed ingestion utilities. |
| `[aws]` | `boto3` | `S3Loader`. |
| `[azure-blob]` | `azure-core`, `azure-identity`, `azure-storage-blob` | `AzureBlobLoader`. |
| `[gcp]` | `google-cloud-storage` | `GCSLoader`. |
| `[sql]` | `sqlalchemy` | `SQLLoader`. |

---

## Store backends

The retrieval pipeline ships three vector store backends. The
in-memory backend is included in `[retrieval-core]`; the others are
opt-in:

| Extra | Backend | Notes |
|---|---|---|
| (none) | `InMemoryBackend` | Already in `[retrieval-core]`. Useful for tests and small corpora. |
| `[stores-vector]` | `PgvectorBackend` | Adds `asyncpg`, `pgvector`. Requires a Postgres instance with the `pgvector` extension. |
| `[stores-chroma]` | `ChromaBackend` | Adds `chromadb`. |
| `[stores-all]` | both | Convenience umbrella for the two persistent backends. |

---

## System-level dependencies

A few extras need things that aren't on PyPI:

- **`[ocr]`**: The `pytesseract` Python wrapper needs the Tesseract
  binary installed and on `PATH`. See the
  [Tesseract install guide](https://tesseract-ocr.github.io/tessdoc/Installation.html).
- **`[stores-vector]`**: `asyncpg`/`pgvector` need a running Postgres
  with the `pgvector` extension enabled.

---

## What about `[all]`?

`railtracks[all]` does **not** include the retrieval stack. It covers
the rest of railtracks (visualizer, Portkey integration). Install
`[retrieval]` (or `[retrieval-core]` + targeted extras) alongside if
you need both.
