# Ingestion components

A **document loader** reads raw data from a source (a file, directory,
URL, database, dataset) and produces [`Document`](#the-document-object)
objects. Loaders are stage one of the pipeline; everything downstream
(chunkers, embedders, stores) consumes `Document`s.

For the streaming-and-safety side of ingestion (events, re-ingest,
multi-tenant writes, sanitization), see the [Ingestion page](../../runtime/ingestion.md).

---

## The Document object

Every loader produces `Document` instances. ([Document API Reference](../../../api_reference/railtracks/retrieval.html#Document))

`source` is the natural identity of a document for re-ingest staleness
checks. Loaders that read files set it to the file path; HTTP loaders set
it to the URL; the Hugging Face loader sets it to `{dataset}/{split}`. If
you write a custom loader and want skip-by-hash idempotency, set `source`
to something stable.

---

## Built-in loaders

| Loader | Handles | Extra install |
|---|---|---|
| `TextLoader` | `.txt`, `.md` files & directories | None |
| `CSVLoader`  | `.csv` files & directories | None |
| `JSONLoader` | `.json` and `.jsonl` files & directories | None |
| `PyPDFLoader` | `.pdf` files & directories (embedded text only) | `pip install "railtracks[pdf]"` |
| `PyPDFOCRLoader` | `.pdf` files & directories with OCR fallback | `pip install "railtracks[ocr]"` + [Tesseract](https://pypi.org/project/pytesseract/) |
| `HuggingFaceDatasetLoader` | Hugging Face Hub datasets (streaming) | `pip install "railtracks[huggingface]"` |
| `LangChainLoaderAdapter` | Any LangChain loader | Depends on wrapped loader |

`TextLoader`, `CSVLoader`, `JSONLoader`, `SanitizingLoader`, and the base
classes are re-exported from `railtracks.retrieval.loaders`. The optional
loaders (PDF, OCR, Hugging Face) live under their own submodules; import
them directly to avoid pulling in optional dependencies you don't need.

---

## The unified loader interface

All loaders share three methods. **Prefer `astream()` for anything that
might not fit in memory**: it's the only path that interleaves with
chunking/embedding/storage:

```python
--8<-- "docs/scripts/retrieval/ingestion_example.py:base"
```

`load()` and `aload()` are convenience wrappers around `astream()`. They
collect everything into a list before returning, so use them only when
you don't anticipate memory constraints.

---

## Next steps

| You want to… | Read |
|---|---|
| See the built-in loaders (text, CSV, JSON, PDF, OCR, Hugging Face) | [Built-in loaders](methods.md) |
| Check out [Integrations](../../../integrations/storage/overview.md) for loaders that read data from cloud services (ie AWS S3, Azure Blob, etc) |
| Write your own loader for an unsupported source | [Custom loaders](methods.md#custom-loaders) |
| Run the pipeline end-to-end | [Ingestion](../../runtime/ingestion.md) (write path) |
