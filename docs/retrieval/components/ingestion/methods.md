# Loading: Built-in loaders

Six loaders ship under `railtracks.retrieval.loaders`. Pick one based on
your source format, and reach for a [custom loader](#custom-loaders) when
none of these fit.

---

## Summary

| Loader | Source | One Document per | Extras |
|---|---|---|---|
| `TextLoader` | `.txt` / `.md` files (or directories) | File | None |
| `CSVLoader` | `.csv` files (or directories) | Row | None |
| `JSONLoader` | `.json` and `.jsonl` files (or directories) | Top-level object / one per line | None |
| `PyPDFLoader` | PDFs with a text layer | Page (default) or whole file | `railtracks[pdf]` |
| `PyPDFOCRLoader` | PDFs that include scanned images | Page (default) or whole file | `railtracks[ocr]` + Tesseract binary |
| `HuggingFaceDatasetLoader` | Any dataset on the [HF Hub](https://huggingface.co/datasets) | Row | `railtracks[huggingface]` |

Every loader exposes the same triple: `load()` (sync, materializes
everything), `aload()` (async, materializes everything), `astream()`
(async generator). For corpora larger than memory, always reach for
`astream()`.

---

## `TextLoader`

Reads `.txt` and `.md` files. Markdown files auto-get `type="markdown"`,
which lets downstream chunkers (`MarkdownHeaderChunker`) pick heading-aware
splitting.

```python
--8<-- "docs/scripts/retrieval/ingestion_example.py:text_single_file"
```

```python
--8<-- "docs/scripts/retrieval/ingestion_example.py:text_directory"
```

Directories are walked recursively; files are returned in sorted-path
order for deterministic re-ingest. Default encoding is `utf-8-sig`
(BOM-aware), which beats `utf-8` for legacy corpora without slowing the
common case.

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `file_path` | `str` | required | Path to a `.txt`/`.md` file or directory |
| `encoding` | `str` | `"utf-8-sig"` | File encoding (BOM-aware) |

**Document metadata**: `file_type` (`.txt` or `.md`), `encoding`.

---

## `CSVLoader`

One Document per row. Columns can go into `content` (searchable) or
`metadata` (filterable, not embedded).

```python
--8<-- "docs/scripts/retrieval/ingestion_example.py:csv_basic"
```

With no column config, **every column ends up in `content`**: usually
not what you want. IDs, timestamps, and foreign keys add noise without
helping retrieval. Use `content_columns` to be explicit:

```python
--8<-- "docs/scripts/retrieval/ingestion_example.py:csv_content_columns"
```

Columns *not* in `content_columns` automatically become metadata. Use
`ignore_columns` to drop fields entirely (PII, audit timestamps).

Additionally you can decide what you want to use as a _separator_ for merging columns when loading:
```python
--8<-- "docs/scripts/retrieval/ingestion_example.py:csv_separator"
```
**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `file_path` | `str` | required | Path to a `.csv` file or directory |
| `content_columns` | `list[str] | None` | `None` | Columns joined into `content`. `None` = all columns. |
| `ignore_columns` | `list[str] | None` | `None` | Columns dropped entirely |
| `content_separator` | `str` | `"\n"` | Used to join content-column values |
| `encoding` | `str` | `"utf-8-sig"` | File encoding |

**Document metadata**: `row_index` plus every column not in
`content_columns` or `ignore_columns`.

---

## `JSONLoader`

Handles two formats, picked by suffix:

- `.json` — root is a single object or an array of objects.
- `.jsonl` — one JSON object per line (blank lines skipped). Streamed
  line by line, so reach for `.jsonl` whenever the corpus is larger
  than memory.

Each object — array element or JSONL line — becomes one `Document`.

```python
--8<-- "docs/scripts/retrieval/ingestion_example.py:json_loader"
```

For `.jsonl`:

```python
--8<-- "docs/scripts/retrieval/ingestion_example.py:jsonl_loader"
```

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `file_path` | `str` | required | Path to a `.json` / `.jsonl` file, or a directory containing them |
| `content_keys` | `list[str] | "*"` | `"*"` | Keys whose values form `content`. `"*"` serialises the whole object. |
| `id_key` | `str | None` | `None` | Top-level key whose value is the per-object id in `Document.source`. Falls back to position (array index or JSONL line). |
| `ignore_keys` | `list[str] | None` | `None` | Keys dropped entirely |
| `content_separator` | `str` | `"\n"` | Used to join content-key values |
| `encoding` | `str` | `"utf-8-sig"` | File encoding |

---

## `PyPDFLoader`

For PDFs with embedded text. Pages with no text layer (scanned images)
return empty; for mixed corpora reach for `PyPDFOCRLoader` instead.

```bash
pip install "railtracks[pdf]"
```

```python
--8<-- "docs/scripts/retrieval/ingestion_example.py:pdf_basic"
```

### Breakdown strategy

`"page"` (the default) emits one Document per page. Page numbers end up
in metadata, citations become trivial, and the chunker decides
per-page rather than across a 200-page file. **Use page strategy for
retrieval.**

```python
--8<-- "docs/scripts/retrieval/ingestion_example.py:pdf_page_strategy"
```

`"document"` emits a single Document for the whole PDF; only useful when
the PDF is small enough to chunk as one unit, or you want custom
splitting that crosses pages.

```python
--8<-- "docs/scripts/retrieval/ingestion_example.py:pdf_document_strategy"
```

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `file_path` | `str` | required | Path to a `.pdf` file or directory |
| `breakdown_strategy` | `"page" \| "document"` | `"page"` | How to split the PDF |

**Document metadata** (page strategy): `page` (1-based), `total_pages`,
`file_type` (`.pdf`).

---

## `PyPDFOCRLoader`

For PDFs with scanned-image pages. Per page, tries pypdf text extraction
first (fast), falls back to Tesseract OCR if extraction returns empty.
Mixed PDFs work transparently.

### Installation

Two pieces: a Python extra and a system binary.

```bash
pip install "railtracks[ocr]"
```

Tesseract is OS-level; pip can't install it. Follow the [official
instructions](https://tesseract-ocr.github.io/tessdoc/Installation.html),
then verify in a fresh terminal:

```bash
tesseract --version
```

### Usage

```python
--8<-- "docs/scripts/retrieval/ingestion_example.py:pdf_ocr_basic"
```

Some PDFs have a garbled or incomplete text layer that pypdf will happily
return. `force_ocr=True` skips the fast path and re-OCRs unconditionally:

```python
--8<-- "docs/scripts/retrieval/ingestion_example.py:pdf_ocr_force"
```

```python
--8<-- "docs/scripts/retrieval/ingestion_example.py:pdf_ocr_document_strategy"
```

`ocr_pages` (document strategy) is the sorted list of 1-based page
numbers that required OCR; useful for auditing how much of a corpus
needed image-based extraction.

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `file_path` | `str` | required | Path to a `.pdf` file or directory |
| `breakdown_strategy` | `"page" \| "document"` | `"page"` | How to split the PDF |
| `force_ocr` | `bool` | `False` | OCR every page, skipping fast path |
| `dpi` | `int` | `300` | OCR render resolution; 300 is Tesseract's sweet spot |
| `language` | `str` | `"eng"` | Tesseract language code (`"eng+deu"`, `"jpn"`, etc.) |

**Document metadata**: `page`, `total_pages`, `file_type`, `ocr`
(page-strategy boolean), `ocr_pages` (document-strategy list).

!!! tip "Tesseract limitations"
    Tesseract handles clean printed text well, struggles with
    handwriting, low-quality scans, and complex layouts (tables, forms).
    The [`BaseOCRLoader`](https://github.com/RailtownAI/railtracks/blob/main/packages/railtracks/src/railtracks/retrieval/loaders/base_ocr.py)
    abstraction lets future loaders plug in cloud OCR or LLM-vision
    engines by overriding `_ocr_image`.

---

## `HuggingFaceDatasetLoader`
!!! warning "Early-exit hang with `HuggingFaceDatasetLoader`"
    Breaking out of `astream()` before the dataset is exhausted may cause the Python process to hang at shutdown. This is an upstream parquet-streaming bug in [`datasets`](https://github.com/huggingface/datasets) on `pyarrow <= 24`, see [huggingface/datasets#8176](https://github.com/huggingface/datasets/pull/8176) (fixes [#8169](https://github.com/huggingface/datasets/issues/8169) and [#7467](https://github.com/huggingface/datasets/issues/7467)). Workaround: call `gc.collect()` after you stop iterating, or upgrade to a `pyarrow` release that ships the underlying [arrow#45214](https://github.com/apache/arrow/issues/45214) fix.

Streams rows from any dataset on the [Hugging Face Hub](https://huggingface.co/datasets).
One Document per row, fetched lazily.

```bash
pip install "railtracks[huggingface]"
```

```python
--8<-- "docs/scripts/retrieval/ingestion_example.py:hf_basic"
```

**Always use `astream()` here.** `aload()` / `load()` materialize the
whole split before returning; fine for tiny demo datasets, disastrous
for `ag_news` or anything Common Crawl–scale.

Many QA datasets split "the text" across columns (`question` + `context`,
`title` + `body`). Pass them all to `content_columns`:

```python
--8<-- "docs/scripts/retrieval/ingestion_example.py:hf_multi_column"
```

`metadata_columns` are copied into `Document.metadata` as-is. **Anything
not in `content_columns` or `metadata_columns` is dropped**; be explicit
about what you want:

```python
--8<-- "docs/scripts/retrieval/ingestion_example.py:hf_metadata_columns"
```

For subsets, revisions, or gated datasets, `dataset_kwargs` is forwarded
straight to `datasets.load_dataset`:

```python
--8<-- "docs/scripts/retrieval/ingestion_example.py:hf_kwargs"
```

For gated datasets set `HF_TOKEN` in your environment, or pass
`dataset_kwargs={"token": "hf_xxxxxxx"}`.

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `dataset_name` | `str` | required | Dataset name on the Hub |
| `split` | `str` | required | Split to stream (`"train"`, `"validation"`, etc.) |
| `content_columns` | `list[str]` | required | Columns joined into `content`. Must be non-empty. |
| `metadata_columns` | `list[str] \| None` | `None` | Columns copied into `metadata` |
| `content_separator` | `str` | `"\n"` | Used to join `content_columns` values |
| `dataset_kwargs` | `dict \| None` | `None` | Forwarded to `datasets.load_dataset` |

**Document metadata**: `row_index` plus any column listed in
`metadata_columns`. `Document.source` is `"{dataset_name}/{split}"`.

---
# LangChain Loaders

`LangChainLoaderAdapter` wraps any [LangChain `BaseLoader`](https://reference.langchain.com/python/langchain-community/document_loaders) and normalises its output to railtracks' [`Document`](base.md/#the-document-object) model. This unlocks LangChain's large community loader ecosystem (Wikipedia, Notion, Confluence, S3, Slack, …) without having to re-implement any of them in railtracks.

The adapter does not import `langchain` itself — it duck-types on the wrapped loader. Install whichever LangChain package provides the loader you want:

```bash
pip install langchain-community
```

```python
from langchain_community.document_loaders import WikipediaLoader
```

---

## Basic Usage

```python
--8<-- "docs/scripts/retrieval/ingestion_example.py:pdf_basic"
```

Each LangChain `Document` becomes one railtracks `Document`:

- `page_content` → `Document.content`
- `metadata["source"]` is popped into `Document.source` (if present)
- The remaining `metadata` is copied across as-is

---

## Tagging the Document Type

LangChain loaders are source-agnostic, so the adapter cannot guess the right `DocumentType`. Pass it explicitly when you know what you're loading:

```python
--8<-- "docs/scripts/retrieval/ingestion_example.py:pdf_basic"
```

The default is `DocumentType.TEXT`.

---

## Overriding the Source

If the wrapped loader doesn't populate `metadata["source"]` or you'd like a more meaningful label, pass `source=` to the adapter. The explicit value wins and metadata is left untouched:

```python
--8<-- "docs/scripts/retrieval/ingestion_example.py:langchain_adapter_init"
```

---

## Streaming Behaviour

The adapter tries to stream rather than buffer, falling back gracefully when the wrapped loader doesn't support async or lazy iteration:

| Wrapped loader exposes | Adapter uses | Streams? |
|------------------------|--------------|----------|
| `alazy_load`           | `alazy_load` directly | Yes (native async) |
| `lazy_load` only       | `lazy_load` pumped from a worker thread | Yes |
| `load` only            | `load()` once, then iterates the result | No (eager) |

Every modern LangChain `BaseLoader` provides at least the default `alazy_load`, so the streaming path is the common case.

---

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `loader` | `Any` | — | A LangChain `BaseLoader`-compatible instance. |
| `document_type` | `DocumentType` | `DocumentType.TEXT` | Tag applied to every emitted document. |
| `source` | `str \| None` | `None` | Overrides `Document.source`. When `None`, the adapter falls back to `metadata["source"]`. |

---

## When to Reach for the Adapter

Use `LangChainLoaderAdapter` when:

- A loader you need already exists in `langchain-community` (Notion, Slack, Confluence, Sitemap, GitHub issues, …) and re-implementing it would be wasted effort.
- You're migrating a LangChain-based ingestion pipeline to railtracks and want to keep the existing loaders working unchanged.

Reach for a native railtracks loader (`TextLoader`, `PyPDFLoader`, `HuggingFaceDatasetLoader`, …) when one exists — they're better integrated and don't carry a third-party dependency.

---

## Choosing a loader

| Situation | Start with |
|---|---|
| Plain text or markdown files on disk | `TextLoader` |
| Tabular rows (one document per row) | `CSVLoader` |
| Hand-curated structured data | `JSONLoader` |
| PDFs that came from a digital source | `PyPDFLoader` |
| PDFs from scans, photos, or unknown provenance | `PyPDFOCRLoader` |
| Public NLP datasets, benchmarks, large corpora | `HuggingFaceDatasetLoader` |
| Anything else (DB row, API response, queue) | [Custom loader](#custom-loaders) |

---

## Custom loaders

When the built-ins don't cover your source (a database table, an
internal API, a message queue), subclass `BaseDocumentLoader` and
implement `astream()`. `aload()` and `load()` come for free.

```python
--8<-- "docs/scripts/retrieval/ingestion_example.py:custom_loader"
```

Use it like any other loader:

```python
--8<-- "docs/scripts/retrieval/ingestion_example.py:custom_usage"
```

**Don't buffer the corpus.** Yield each `Document` as soon as it's ready
- the streaming pipeline depends on producers handing off work without
materializing everything first. Buffering at your source breaks
back-pressure for every downstream stage.

### Wrapping a synchronous source

If your source only has a blocking API, push it to a worker thread with
`asyncio.to_thread()`:

```python
--8<-- "docs/scripts/retrieval/ingestion_example.py:custom_sync_wrap"
```

### Set `source` for free idempotency

Set `Document.source` to something stable: a path, a URL, a primary key.
The runtime hashes content and pairs it with `source` to skip re-ingest
of unchanged documents. Without a stable `source`, every run looks
"new" and you pay for embedding the same content repeatedly.

---

## See also

- [Loading overview](base.md): the `Document` object, `BaseDocumentLoader`
  contract, the loader → chunker handoff.
- [Chunking methods](../chunking/methods.md): what to do with the
  `Document`s these loaders produce.
- [`SanitizingLoader`](../../runtime/ingestion.md#sanitizing-loaders) -
  wrap any loader to redact PII before chunking.
