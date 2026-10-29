# Loading: Built-in loaders

Six loaders ship under `railtracks.retrieval.loaders`. Pick one based on your source format, and reach for a [custom loader](#custom-loaders) when none of these fit.

______________________________________________________________________

## Summary

| Loader                     | Source                                                       | One Document per                | Extras                               |
| -------------------------- | ------------------------------------------------------------ | ------------------------------- | ------------------------------------ |
| `TextLoader`               | `.txt` / `.md` files (or directories)                        | File                            | None                                 |
| `CSVLoader`                | `.csv` files (or directories)                                | Row                             | None                                 |
| `JSONLoader`               | `.json` and `.jsonl` files (or directories)                  | Top-level object / one per line | None                                 |
| `PyPDFLoader`              | PDFs with a text layer                                       | Page (default) or whole file    | `railtracks[pdf]`                    |
| `PyPDFOCRLoader`           | PDFs that include scanned images                             | Page (default) or whole file    | `railtracks[ocr]` + Tesseract binary |
| `HuggingFaceDatasetLoader` | Any dataset on the [HF Hub](https://huggingface.co/datasets) | Row                             | `railtracks[huggingface]`            |

Every loader exposes the same triple: `load()` (sync, materializes everything), `aload()` (async, materializes everything), `astream()` (async generator). For corpora larger than memory, always reach for `astream()`.

______________________________________________________________________

## `TextLoader`

Reads `.txt` and `.md` files. Markdown files auto-get `type="markdown"`, which lets downstream chunkers (`MarkdownHeaderChunker`) pick heading-aware splitting.

```python
from railtracks.retrieval.loaders import TextLoader



loader = TextLoader("notes.txt")
docs = loader.load()

doc = docs[0]
print(doc.content)            # full file text
print(doc.type)               # "text" or "markdown"
print(doc.source)             # "notes.txt"
print(doc.metadata)           # {"file_type": ".txt", "encoding": "utf-8-sig"}
```

```python
# Recursively loads .txt and .md files, sorted by path.
docs = TextLoader("knowledge_base/").load()
print(len(docs))
print(docs[0].source)
```

Directories are walked recursively; files are returned in sorted-path order for deterministic re-ingest. Default encoding is `utf-8-sig` (BOM-aware), which beats `utf-8` for legacy corpora without slowing the common case.

**Parameters**

| Parameter   | Type  | Default       | Description                              |
| ----------- | ----- | ------------- | ---------------------------------------- |
| `file_path` | `str` | required      | Path to a `.txt`/`.md` file or directory |
| `encoding`  | `str` | `"utf-8-sig"` | File encoding (BOM-aware)                |

**Document metadata**: `file_type` (`.txt` or `.md`), `encoding`.

______________________________________________________________________

## `CSVLoader`

One Document per row. Columns can go into `content` (searchable) or `metadata` (filterable, not embedded).

```python
from railtracks.retrieval.loaders import CSVLoader



# Every row becomes a Document. By default, all columns end up in content.
docs = CSVLoader("products.csv").load()

doc = docs[0]
print(doc.content)   # "name: Widget\nprice: 9.99\ndescription: ..."
print(doc.type)      # "csv"
print(doc.metadata)  # {"row_index": 0}
```

With no column config, **every column ends up in `content`**: usually not what you want. IDs, timestamps, and foreign keys add noise without helping retrieval. Use `content_columns` to be explicit:

```python
# Columns in content_columns form the searchable text.
# Everything else automatically becomes metadata (filterable downstream).
loader = CSVLoader(
    "products.csv",
    content_columns=["name", "description"],
)
docs = loader.load()
print(docs[0].content)   # "name: Widget\ndescription: ..."
print(docs[0].metadata)  # {"price": "9.99", "row_index": 0}
```

Columns *not* in `content_columns` automatically become metadata. Use `ignore_columns` to drop fields entirely (PII, audit timestamps).

Additionally you can decide what you want to use as a *separator* for merging columns when loading:

```python
# Default content_separator is "\n". Change it for single-line records.
CSVLoader(
    "products.csv",
    content_columns=["name", "description"],
    content_separator=" | ",
)
```

**Parameters**

| Parameter           | Type        | Default       | Description                        |
| ------------------- | ----------- | ------------- | ---------------------------------- |
| `file_path`         | `str`       | required      | Path to a `.csv` file or directory |
| `content_columns`   | \`list[str] | None\`        | `None`                             |
| `ignore_columns`    | \`list[str] | None\`        | `None`                             |
| `content_separator` | `str`       | `"\n"`        | Used to join content-column values |
| `encoding`          | `str`       | `"utf-8-sig"` | File encoding                      |

**Document metadata**: `row_index` plus every column not in `content_columns` or `ignore_columns`.

______________________________________________________________________

## `JSONLoader`

Handles two formats, picked by suffix:

- `.json` — root is a single object or an array of objects.
- `.jsonl` — one JSON object per line (blank lines skipped). Streamed line by line, so reach for `.jsonl` whenever the corpus is larger than memory.

Each object — array element or JSONL line — becomes one `Document`.

```python
from railtracks.retrieval.loaders import JSONLoader

# Root must be an object or array of objects. content_keys selects which
# keys form the searchable text; ignore_keys drops keys entirely.
docs = JSONLoader(
    "articles.json",
    content_keys=["title", "body"],
    ignore_keys=["internal_id"],
).load()

print(docs[0].content)   # "title: Getting started\nbody: ..."
print(docs[0].metadata)  # {"author": "Alice", "index": 0}
```

Nested values can be normalized before embedding with a content extractor:

```python
from railtracks.retrieval import JsonExtractor
from railtracks.retrieval.loaders import JSONLoader

# Preserve a nested field as valid JSON instead of Python's dict repr.
JSONLoader(
    "questions.json",
    content_keys=["question"],
    content_extractor=JsonExtractor(),
)
```

For `.jsonl`:

```python
from railtracks.retrieval.loaders import JSONLoader

# JSONL: one JSON object per line. Streamed line by line — safe for
# corpora larger than memory. Use id_key for stable Document IDs across
# re-ingestion when objects may be reordered.
async def jsonl_stream():
    async for doc in JSONLoader(
        "events.jsonl",
        content_keys=["title", "body"],
        id_key="_id",
    ).astream():
        print(doc.source)  # "events.jsonl#<_id>"
```

**Parameters**

| Parameter           | Type                       | Default       | Description                                                                                                              |
| ------------------- | -------------------------- | ------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `file_path`         | `str`                      | required      | Path to a `.json` / `.jsonl` file, or a directory containing them                                                        |
| `content_keys`      | `list[str] \| "*"`         | `"*"`         | Keys whose values form `content`. `"*"` serialises the whole object.                                                     |
| `id_key`            | `str \| None`              | `None`        | Top-level key whose value is the per-object id in `Document.source`. Falls back to position (array index or JSONL line). |
| `ignore_keys`       | `list[str] \| None`        | `None`        | Keys dropped entirely                                                                                                    |
| `content_separator` | `str`                      | `"\n"`        | Used to join content-key values                                                                                          |
| `encoding`          | `str`                      | `"utf-8-sig"` | File encoding                                                                                                            |
| `content_extractor` | `ContentExtractor \| None` | `None`        | Converts selected values to text. Omitted preserves existing serialization.                                              |

______________________________________________________________________

## `PyPDFLoader`

For PDFs with embedded text. Pages with no text layer (scanned images) return empty; for mixed corpora reach for `PyPDFOCRLoader` instead.

```bash
pip install "railtracks[pdf]"
```

```python
# Requires: pip install "railtracks[pdf]"
from railtracks.retrieval.loaders.pdf_loader import PyPDFLoader

docs = PyPDFLoader("report.pdf").load()
doc = docs[0]
print(doc.content)   # extracted text from page 1
print(doc.type)      # "pdf"
print(doc.metadata)  # {"page": 1, "total_pages": 42, "file_type": ".pdf"}
```

### Breakdown strategy

`"page"` (the default) emits one Document per page. Page numbers end up in metadata, citations become trivial, and the chunker decides per-page rather than across a 200-page file. **Use page strategy for retrieval.**

```python
from railtracks.retrieval.loaders.pdf_loader import PyPDFLoader

# One Document per page. Best for retrieval — keeps page numbers in
# metadata, which makes citations trivial.
docs = PyPDFLoader("report.pdf", breakdown_strategy="page").load()
print(len(docs))              # number of pages
print(docs[0].metadata)       # {"page": 1, "total_pages": 42, "file_type": ".pdf"}
```

`"document"` emits a single Document for the whole PDF; only useful when the PDF is small enough to chunk as one unit, or you want custom splitting that crosses pages.

```python
from railtracks.retrieval.loaders.pdf_loader import PyPDFLoader

# Single Document. Pages joined with "\n\n". Use only when the whole PDF
# is small enough to chunk together or you want to apply custom splitting.
docs = PyPDFLoader("report.pdf", breakdown_strategy="document").load()
print(len(docs))        # always 1
```

**Parameters**

| Parameter            | Type                                  | Default  | Description                        |
| -------------------- | ------------------------------------- | -------- | ---------------------------------- |
| `file_path`          | `str`                                 | required | Path to a `.pdf` file or directory |
| `breakdown_strategy` | `"page" \| "paragraph" \| "document"` | `"page"` | How to split the PDF               |

**Document metadata** (page strategy): `page` (1-based), `total_pages`, `file_type` (`.pdf`).

The `"paragraph"` strategy emits one Document per non-empty paragraph on each page, splitting on double newlines. Its metadata additionally includes `paragraph` (1-based within the page), which makes paragraph-level citations possible.

______________________________________________________________________

## `PyPDFOCRLoader`

For PDFs with scanned-image pages. Per page, tries pypdf text extraction first (fast), falls back to Tesseract OCR if extraction returns empty. Mixed PDFs work transparently.

### Installation

Two pieces: a Python extra and a system binary.

```bash
pip install "railtracks[ocr]"
```

Tesseract is OS-level; pip can't install it. Follow the [official instructions](https://tesseract-ocr.github.io/tessdoc/Installation.html), then verify in a fresh terminal:

```bash
tesseract --version
```

### Usage

```python
# Requires: pip install "railtracks[ocr]" + Tesseract on PATH.
from railtracks.retrieval.loaders.pdf_ocr_loader import PyPDFOCRLoader

docs = PyPDFOCRLoader("scanned_invoice.pdf").load()
doc = docs[0]
print(doc.content)         # OCR'd or pypdf-extracted text
print(doc.metadata["ocr"]) # True if OCR was used for this page
```

Some PDFs have a garbled or incomplete text layer that pypdf will happily return. `force_ocr=True` skips the fast path and re-OCRs unconditionally:

```python
from railtracks.retrieval.loaders.pdf_ocr_loader import PyPDFOCRLoader

# Skip the text-extraction fast path. Useful when pypdf returns a
# garbled or incomplete text layer that you'd rather re-OCR.
docs = PyPDFOCRLoader("messy_scan.pdf", force_ocr=True).load()
assert all(d.metadata["ocr"] for d in docs)
```

```python
from railtracks.retrieval.loaders.pdf_ocr_loader import PyPDFOCRLoader

docs = PyPDFOCRLoader("report.pdf", breakdown_strategy="document").load()
print(docs[0].metadata)
    # {"total_pages": 42, "file_type": ".pdf", "ocr_pages": [3, 7, 8]}
```

`ocr_pages` (document strategy) is the sorted list of 1-based page numbers that required OCR; useful for auditing how much of a corpus needed image-based extraction.

**Parameters**

| Parameter            | Type                   | Default  | Description                                          |
| -------------------- | ---------------------- | -------- | ---------------------------------------------------- |
| `file_path`          | `str`                  | required | Path to a `.pdf` file or directory                   |
| `breakdown_strategy` | `"page" \| "document"` | `"page"` | How to split the PDF                                 |
| `force_ocr`          | `bool`                 | `False`  | OCR every page, skipping fast path                   |
| `dpi`                | `int`                  | `300`    | OCR render resolution; 300 is Tesseract's sweet spot |
| `language`           | `str`                  | `"eng"`  | Tesseract language code (`"eng+deu"`, `"jpn"`, etc.) |

**Document metadata**: `page`, `total_pages`, `file_type`, `ocr` (page-strategy boolean), `ocr_pages` (document-strategy list).

Tesseract limitations

Tesseract handles clean printed text well, struggles with handwriting, low-quality scans, and complex layouts (tables, forms). The [`BaseOCRLoader`](https://github.com/RailtownAI/railtracks/blob/main/packages/railtracks/src/railtracks/retrieval/loaders/base_ocr.py) abstraction lets future loaders plug in cloud OCR or LLM-vision engines by overriding `_ocr_image`.

______________________________________________________________________

## `HuggingFaceDatasetLoader`

Early-exit hang with `HuggingFaceDatasetLoader`

Breaking out of `astream()` before the dataset is exhausted may cause the Python process to hang at shutdown. This is an upstream parquet-streaming bug in [`datasets`](https://github.com/huggingface/datasets) on `pyarrow <= 24`, see [huggingface/datasets#8176](https://github.com/huggingface/datasets/pull/8176) (fixes [#8169](https://github.com/huggingface/datasets/issues/8169) and [#7467](https://github.com/huggingface/datasets/issues/7467)). Workaround: call `gc.collect()` after you stop iterating, or upgrade to a `pyarrow` release that ships the underlying [arrow#45214](https://github.com/apache/arrow/issues/45214) fix.

Streams rows from any dataset on the [Hugging Face Hub](https://huggingface.co/datasets). One Document per row, fetched lazily.

```bash
pip install "railtracks[huggingface]"
```

```python
async def hf_basic():
    # Requires: pip install "railtracks[huggingface]"
    from railtracks.retrieval.loaders.huggingface_loader import HuggingFaceDatasetLoader

    loader = HuggingFaceDatasetLoader(
        dataset_name="ag_news",
        split="test",
        content_columns=["text"],
    )
    # Rows are streamed; use astream() for anything larger than memory.
    async for doc in loader.astream():
        print(doc.content[:80])
        print(doc.source)    # "ag_news/test"
        print(doc.metadata)  # {"row_index": 0}
```

**Always use `astream()` here.** `aload()` / `load()` materialize the whole split before returning; fine for tiny demo datasets, disastrous for `ag_news` or anything Common Crawl–scale.

Many QA datasets split "the text" across columns (`question` + `context`, `title` + `body`). Pass them all to `content_columns`:

```python
from railtracks.retrieval.loaders.huggingface_loader import HuggingFaceDatasetLoader

# Many datasets split "the text" across columns. Join them with
# content_separator instead of stitching things yourself downstream.
HuggingFaceDatasetLoader(
    dataset_name="squad",
    split="validation",
    content_columns=["question", "context"],
    content_separator="\n\n",
)
```

`metadata_columns` are copied into `Document.metadata` as-is. **Anything not in `content_columns` or `metadata_columns` is dropped**; be explicit about what you want:

```python
from railtracks.retrieval.loaders.huggingface_loader import HuggingFaceDatasetLoader

# metadata_columns are copied into Document.metadata for later filtering
# or citation. Anything not in content_columns or metadata_columns is dropped.
HuggingFaceDatasetLoader(
    dataset_name="squad",
    split="validation",
    content_columns=["question", "context"],
    metadata_columns=["title", "id"],
)
```

For subsets, revisions, or gated datasets, `dataset_kwargs` is forwarded straight to `datasets.load_dataset`:

```python
from railtracks.retrieval import ProseExtractor
from railtracks.retrieval.loaders.huggingface_loader import HuggingFaceDatasetLoader

# dataset_kwargs is forwarded straight to datasets.load_dataset.
# ms_marco's passages field is nested, so ProseExtractor turns its structure
# into labelled searchable text while metadata values remain unchanged.
HuggingFaceDatasetLoader(
    dataset_name="ms_marco",
    split="validation",
    content_columns=["query", "passages"],
    dataset_kwargs={"name": "v2.1"},
    content_extractor=ProseExtractor(),
)
```

For gated datasets set `HF_TOKEN` in your environment, or pass `dataset_kwargs={"token": "hf_xxxxxxx"}`.

**Parameters**

| Parameter           | Type                       | Default  | Description                                                                       |
| ------------------- | -------------------------- | -------- | --------------------------------------------------------------------------------- |
| `dataset_name`      | `str`                      | required | Dataset name on the Hub                                                           |
| `split`             | `str`                      | required | Split to stream (`"train"`, `"validation"`, etc.)                                 |
| `content_columns`   | `list[str]`                | required | Columns joined into `content`. Must be non-empty.                                 |
| `metadata_columns`  | `list[str] \| None`        | `None`   | Columns copied into `metadata`                                                    |
| `content_separator` | `str`                      | `"\n"`   | Used to join `content_columns` values                                             |
| `dataset_kwargs`    | `dict \| None`             | `None`   | Forwarded to `datasets.load_dataset`                                              |
| `content_extractor` | `ContentExtractor \| None` | `None`   | Converts each selected content-column value to text. Omitted uses `StrExtractor`. |

**Document metadata**: `row_index` plus any column listed in `metadata_columns`. `Document.source` is `"{dataset_name}/{split}"`.

## Structured content extractors

Both `JSONLoader` and `HuggingFaceDatasetLoader` accept any callable matching `ContentExtractor`: it receives one selected value and returns a string. The built-ins are importable from `railtracks.retrieval`:

- `StrExtractor` uses `str(value)` and is the Hugging Face loader default.
- `JsonExtractor` produces valid JSON and preserves Unicode text.
- `ProseExtractor` renders nested dictionaries and lists as labelled prose, with braces around nested dictionaries and brackets around lists to show their boundaries.

For example, the `passages` column in `ms_marco` is structured. The `hf_kwargs` example above uses `ProseExtractor` so the nested labels and values remain visible in the extracted text, including `is_selected` flags and raw URLs. For retrieval focused on passage content, use a custom extractor that selects only `passage_text`. Extractors apply only to content fields; `metadata_columns` stay as their original Python values.

Extraction failures stop loading and raise a `ValueError` naming the content column or key, zero-based row or object index, and source; the original exception is preserved as the cause. They do not currently produce per-document recovery events. For `JSONLoader(content_keys="*")`, the reported key is `"*"` because the extractor receives the entire filtered object.

______________________________________________________________________

# LangChain Loaders

`LangChainLoaderAdapter` wraps any [LangChain `BaseLoader`](https://reference.langchain.com/python/langchain-community/document_loaders) and normalises its output to railtracks' [`Document`](https://docs.railtracks.org/retrieval/components/ingestion/base/#the-document-object) model. This unlocks LangChain's large community loader ecosystem (Wikipedia, Notion, Confluence, S3, Slack, …) without having to re-implement any of them in railtracks.

The adapter does not import `langchain` itself — it duck-types on the wrapped loader. Install whichever LangChain package provides the loader you want:

```bash
pip install langchain-community
```

```python
from langchain_community.document_loaders import WikipediaLoader
```

______________________________________________________________________

## Basic Usage

```python
# Requires: pip install "railtracks[pdf]"
from railtracks.retrieval.loaders.pdf_loader import PyPDFLoader

docs = PyPDFLoader("report.pdf").load()
doc = docs[0]
print(doc.content)   # extracted text from page 1
print(doc.type)      # "pdf"
print(doc.metadata)  # {"page": 1, "total_pages": 42, "file_type": ".pdf"}
```

Each LangChain `Document` becomes one railtracks `Document`:

- `page_content` → `Document.content`
- `metadata["source"]` is popped into `Document.source` (if present)
- The remaining `metadata` is copied across as-is

______________________________________________________________________

## Tagging the Document Type

LangChain loaders are source-agnostic, so the adapter cannot guess the right `DocumentType`. Pass it explicitly when you know what you're loading:

```python
# Requires: pip install "railtracks[pdf]"
from railtracks.retrieval.loaders.pdf_loader import PyPDFLoader

docs = PyPDFLoader("report.pdf").load()
doc = docs[0]
print(doc.content)   # extracted text from page 1
print(doc.type)      # "pdf"
print(doc.metadata)  # {"page": 1, "total_pages": 42, "file_type": ".pdf"}
```

The default is `DocumentType.TEXT`.

______________________________________________________________________

## Overriding the Source

If the wrapped loader doesn't populate `metadata["source"]` or you'd like a more meaningful label, pass `source=` to the adapter. The explicit value wins and metadata is left untouched:

```python

```

______________________________________________________________________

## Streaming Behaviour

The adapter tries to stream rather than buffer, falling back gracefully when the wrapped loader doesn't support async or lazy iteration:

| Wrapped loader exposes | Adapter uses                            | Streams?           |
| ---------------------- | --------------------------------------- | ------------------ |
| `alazy_load`           | `alazy_load` directly                   | Yes (native async) |
| `lazy_load` only       | `lazy_load` pumped from a worker thread | Yes                |
| `load` only            | `load()` once, then iterates the result | No (eager)         |

Every modern LangChain `BaseLoader` provides at least the default `alazy_load`, so the streaming path is the common case.

______________________________________________________________________

## Parameters

| Parameter       | Type           | Default             | Description                                                                               |
| --------------- | -------------- | ------------------- | ----------------------------------------------------------------------------------------- |
| `loader`        | `Any`          | —                   | A LangChain `BaseLoader`-compatible instance.                                             |
| `document_type` | `DocumentType` | `DocumentType.TEXT` | Tag applied to every emitted document.                                                    |
| `source`        | `str \| None`  | `None`              | Overrides `Document.source`. When `None`, the adapter falls back to `metadata["source"]`. |

______________________________________________________________________

## When to Reach for the Adapter

Use `LangChainLoaderAdapter` when:

- A loader you need already exists in `langchain-community` (Notion, Slack, Confluence, Sitemap, GitHub issues, …) and re-implementing it would be wasted effort.
- You're migrating a LangChain-based ingestion pipeline to railtracks and want to keep the existing loaders working unchanged.

Reach for a native railtracks loader (`TextLoader`, `PyPDFLoader`, `HuggingFaceDatasetLoader`, …) when one exists — they're better integrated and don't carry a third-party dependency.

______________________________________________________________________

## Choosing a loader

| Situation                                      | Start with                       |
| ---------------------------------------------- | -------------------------------- |
| Plain text or markdown files on disk           | `TextLoader`                     |
| Tabular rows (one document per row)            | `CSVLoader`                      |
| Hand-curated structured data                   | `JSONLoader`                     |
| PDFs that came from a digital source           | `PyPDFLoader`                    |
| PDFs from scans, photos, or unknown provenance | `PyPDFOCRLoader`                 |
| Public NLP datasets, benchmarks, large corpora | `HuggingFaceDatasetLoader`       |
| Anything else (DB row, API response, queue)    | [Custom loader](#custom-loaders) |

______________________________________________________________________

## Custom loaders

When the built-ins don't cover your source (a database table, an internal API, a message queue), subclass `BaseDocumentLoader` and implement `astream()`. `aload()` and `load()` come for free.

```python
from collections.abc import AsyncGenerator

from railtracks.retrieval import Document, DocumentType  
from railtracks.retrieval.loaders import BaseDocumentLoader  


class MyDatabaseLoader(BaseDocumentLoader):
    """One Document per row of a database table."""

    def __init__(self, dsn: str, table: str) -> None:
        self._dsn = dsn
        self._table = table

    async def astream(self) -> AsyncGenerator[Document, None]:
        rows = await _async_fetch_rows(self._dsn, self._table)
        for row in rows:
            yield Document(
                content=row["body"],
                type=DocumentType.TEXT,
                source=f"{self._table}:{row['id']}",
                metadata={"author": row["author"], "created_at": row["created_at"]},
            )
```

Use it like any other loader:

```python
loader = MyDatabaseLoader("postgresql://...", table="articles")
# Implementing astream() gets you load() and aload() for free.
loader.load()
```

**Don't buffer the corpus.** Yield each `Document` as soon as it's ready

- the streaming pipeline depends on producers handing off work without materializing everything first. Buffering at your source breaks back-pressure for every downstream stage.

### Wrapping a synchronous source

If your source only has a blocking API, push it to a worker thread with `asyncio.to_thread()`:

```python
class MySyncLoader(BaseDocumentLoader):
    """Wrap a blocking source without blocking the event loop."""

    async def astream(self) -> AsyncGenerator[Document, None]:
        rows = await asyncio.to_thread(_fetch_rows_sync)
        for row in rows:
            yield Document(content=row["text"], type=DocumentType.TEXT)
```

### Set `source` for free idempotency

Set `Document.source` to something stable: a path, a URL, a primary key. The runtime hashes content and pairs it with `source` to skip re-ingest of unchanged documents. Without a stable `source`, every run looks "new" and you pay for embedding the same content repeatedly.

______________________________________________________________________

## See also

- [Loading overview](https://docs.railtracks.org/retrieval/components/ingestion/base/index.md): the `Document` object, `BaseDocumentLoader` contract, the loader → chunker handoff.
- [Chunking methods](https://docs.railtracks.org/retrieval/components/chunking/methods/index.md): what to do with the `Document`s these loaders produce.
- [`SanitizingLoader`](https://docs.railtracks.org/retrieval/runtime/ingestion/#sanitizing-loaders) - wrap any loader to redact PII before chunking.
