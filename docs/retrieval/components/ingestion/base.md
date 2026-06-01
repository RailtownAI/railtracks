# Ingestion components

A **document loader** reads raw data from a source — a file, directory,
URL, database, dataset — and produces [`Document`](#the-document-object)
objects. Loaders are stage one of the pipeline; everything downstream
(chunkers, embedders, stores) consumes `Document`s.

For the streaming-and-safety side of ingestion (events, re-ingest,
multi-tenant writes, sanitization), see the [Ingestion page](../../ingestion.md).

---

## The Document object

Every loader produces `Document` instances:

```python
@dataclass
class Document:
    content: str               # Raw text extracted from the source
    type: DocumentType         # "text", "markdown", "csv", "pdf", "json", "html", "code"
    id: UUID                   # Auto-generated unique identifier
    source: str | None         # File path or URL the document came from
    metadata: dict             # Loader-specific keys (page number, language, …)
```

`source` is the natural identity of a document for re-ingest staleness
checks. Loaders that read files set it to the file path; HTTP loaders set
it to the URL; the Hugging Face loader sets it to `{dataset}/{split}`. If
you write a custom loader and want skip-by-hash idempotency, set `source`
to something stable.

---

## Built-in loaders

| Loader | Handles | Extra install |
|---|---|---|
| `TextLoader` | `.txt`, `.md` files & directories | — |
| `CSVLoader`  | `.csv` files & directories | — |
| `JSONLoader` | `.json` files & directories | — |
| `PyPDFLoader` | `.pdf` files & directories (embedded text only) | `pip install "railtracks[pdf]"` |
| `PyPDFOCRLoader` | `.pdf` files & directories with OCR fallback | `pip install "railtracks[ocr]"` + Tesseract |
| `HTMLLoader` | HTML files & URLs | `pip install "railtracks[html]"` |
| `CodeLoader` | Source code files | — |
| `HuggingFaceDatasetLoader` | Hugging Face Hub datasets (streaming) | `pip install "railtracks[huggingface]"` |
| `LangChainLoaderAdapter` | Any LangChain loader | Depends on wrapped loader |

`TextLoader`, `CSVLoader`, `JSONLoader`, `SanitizingLoader`, and the base
classes are re-exported from `railtracks.retrieval.loaders`. The optional
loaders (PDF, OCR, Hugging Face) live under their own submodules — import
them directly to avoid pulling in optional dependencies you don't need.

---

## The unified loader interface

All loaders share three methods. **Prefer `astream()` for anything that
might not fit in memory** — it's the only path that interleaves with
chunking/embedding/storage:

```python
from railtracks.retrieval.loaders import TextLoader

loader = TextLoader("docs/")

# Sync, returns list[Document]. Fine for tests, small corpora, scripts.
docs = loader.load()

# Async, collects all documents before returning. Same memory profile as load().
docs = await loader.aload()

# Async, yields one Document at a time. The only mode that streams.
async for doc in loader.astream():
    print(doc.source, doc.type, len(doc.content))
```

`load()` and `aload()` are convenience wrappers around `astream()`. They
collect everything into a list before returning, so use them only when
"everything" is small.

---

## Next steps

| You want to… | Read |
|---|---|
| Load text and markdown files | [Text and Markdown](text_markdown.md) |
| Load CSV rows as documents | [CSV](csv.md) |
| Load PDFs (with or without OCR) | [PDFs](pdfs.md) |
| Stream Hugging Face datasets | [Hugging Face Datasets](huggingface.md) |
| Read JSON or write a custom loader | [Custom Ingestors](custom.md) |
| Run the pipeline end-to-end | [Ingestion](../../ingestion.md) (write path) |
