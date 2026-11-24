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
| OCR images and PDFs with GLM-OCR | `[retrieval-core]` + `[glm]` |
| Use a real vector store backend | `[retrieval-core]` + `[stores-vector]`, `[stores-chroma]`, or `[stores-turbovec]` |

---

## Extras

### **`[retrieval-core]`** 

The minimum to run the pipeline. Includes
chunking (`scikit-learn` for semantic chunking; `tiktoken` already ships with railtracks), the basic PDF loader (`pypdf`), and the
`InMemoryBackend` (`numpy`). Use this when you're wiring your own
loader or store and don't want the full integration set.

```bash
pip install "railtracks[retrieval-core]"
```

### **`[retrieval]`**:

`[retrieval-core]` plus the built-in connectors and the ChromaDB and
pgvector backends. `TurbovecBackend` remains a separate opt-in extra because
its platform-specific wheel is not available on Intel macOS. It leaves out
`[glm]` (see below).

```bash
pip install "railtracks[retrieval]"
```

---

## Granular extras

Combine these with `[retrieval-core]` to add specific capabilities.

| Extra | Adds | For |
|---|---|---|
| `[ocr]` | `pypdfium2`, `pytesseract`, `pillow` | OCR fallback in `PyPDFOCRLoader`. Also needs the [Tesseract binary](https://tesseract-ocr.github.io/tessdoc/Installation.html) on `PATH`. |
| `[glm]` | `glmocr` | `GLMOCRLoader` for images and PDFs, via the Zhipu cloud API or a self-hosted GLM-OCR server. Not included in `[retrieval]` or `[all]`. |
| `[huggingface]` | `datasets` | `HuggingFaceDatasetLoader` for streaming HF datasets. |
| `[aws]` | `boto3` | `S3Loader`. Add `[pdf]` to parse PDF objects. |
| `[azure-blob]` | `azure-core`, `azure-identity`, `azure-storage-blob` | `AzureBlobLoader`. Add `[pdf]` to parse PDF objects. |
| `[gcp]` | `google-cloud-storage` | `GCSLoader`. Add `[pdf]` to parse PDF objects. |
| `[sql]` | `sqlalchemy` | `SQLLoader`. |

---

## Store backends

The retrieval pipeline ships four vector store backends. The
in-memory backend is included in `[retrieval-core]`; the others are
opt-in:

| Extra | Backend | Notes |
|---|---|---|
| (none) | `InMemoryBackend` | Already in `[retrieval-core]`. Useful for tests and small corpora. |
| `[stores-vector]` | `PgvectorBackend` | Adds `asyncpg`, `pgvector`. Requires a Postgres instance with the `pgvector` extension. |
| `[stores-chroma]` | `ChromaBackend` | Adds `chromadb`. |
| `[chroma]` | `ChromaBackend` | Alias for `[stores-chroma]`, kept for backwards compatibility. Prefer `[stores-chroma]`. |
| `[stores-all]` | ChromaDB, pgvector | Convenience umbrella for these two persistent backends. |
| `[stores-turbovec]` | `TurbovecBackend` | Optional local compressed-vector backend; see the platform note below. |

!!! note "`[tiktok]`"
    `[tiktok]` is now an empty extra: `tiktoken` comes with railtracks itself. It is kept only so existing install commands keep working; drop it from new installs.

---

## System-level dependencies

A few extras need things that aren't on PyPI:

- **`[ocr]`**: The `pytesseract` Python wrapper needs the Tesseract
  binary installed and on `PATH`. See the
  [Tesseract install guide](https://tesseract-ocr.github.io/tessdoc/Installation.html).
- **`[glm]`**: `glmocr` depends on PyMuPDF, which is licensed under
  AGPL-3.0, so it is only installed when you ask for `[glm]` explicitly.
  The cloud API reads its key from `ZHIPU_API_KEY`.
- **`[stores-vector]`**: `asyncpg`/`pgvector` need a running Postgres
  with the `pgvector` extension enabled.
- **`[stores-turbovec]`**: on x86, Turbovec wheels target x86-64-v2
  (SSE4.2); runtime dispatch uses AVX2/AVX-512 when available and has a
  scalar fallback. The extra is not included in `[retrieval]` or `[all]`.

---

## What about `[all]`?

`railtracks[all]` **includes `[retrieval]`**, alongside the rest of
railtracks (visualizer, Portkey integration, web search). It is the
heaviest default install available: it includes the loaders, connectors,
ChromaDB, and pgvector, but not `TurbovecBackend` or `GLMOCRLoader`.

Reach for `[all]` when you want everything and do not care about
install size. If you only need retrieval, install `[retrieval]`
directly — or `[retrieval-core]` plus targeted extras for the
lightest install that still runs the pipeline.
