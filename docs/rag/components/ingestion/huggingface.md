# Hugging Face Datasets

`HuggingFaceDatasetLoader` streams rows from any [Hugging Face Hub](https://huggingface.co/datasets) dataset and converts each row into a [`Document`](overview.md#the-document-object). Rows are fetched lazily, so this works on datasets that would never fit in memory. It requires the optional `huggingface` extra:

```bash
pip install "railtracks[huggingface]"
```

```python
from railtracks.retrieval.loaders.huggingface_loader import HuggingFaceDatasetLoader
```

---

## Basic Usage

```python
loader = HuggingFaceDatasetLoader(
    dataset_name="ag_news",
    split="test",
    content_columns=["text"],
)

async for doc in loader.astream():
    print(doc.content[:80])
    print(doc.source)    # "ag_news/test"
    print(doc.metadata)  # {"row_index": 0}
```

Each row of the chosen split becomes one `Document`. Use `astream()` for large datasets — `aload()` and `load()` collect everything into memory and should only be used on small splits.

---

## Joining Multiple Columns into Content

Many datasets store the "text" across several columns (question + context, title + body, etc.). Pass them all to `content_columns` and they'll be joined by `content_separator`:

```python
loader = HuggingFaceDatasetLoader(
    dataset_name="squad",
    split="validation",
    content_columns=["question", "context"],
    content_separator="\n\n",
)

# doc.content == "What is RAG?\n\nRetrieval-augmented generation..."
```

---

## Forwarding Metadata Columns

Columns listed in `metadata_columns` are copied into `Document.metadata` as-is — handy for filtering or citation:

```python
loader = HuggingFaceDatasetLoader(
    dataset_name="squad",
    split="validation",
    content_columns=["question", "context"],
    metadata_columns=["title", "id"],
)

# doc.metadata == {"title": "...", "id": "...", "row_index": 0}
```

Anything not in `content_columns` or `metadata_columns` is dropped.

---

## Subsets, Revisions, and Auth

Many HF datasets have multiple configurations (subsets). Pass extra keyword arguments via `dataset_kwargs` — they're forwarded straight to `datasets.load_dataset`:

```python
loader = HuggingFaceDatasetLoader(
    dataset_name="ms_marco",
    split="validation",
    content_columns=["query", "passages"],
    dataset_kwargs={"name": "v2.1"},          # subset selector
)
```

For gated datasets, set `HF_TOKEN` in your environment or pass `dataset_kwargs={"token": "hf_xxxxxxx"}`.

!!! tip
    Streaming mode is enabled by default. To disable it (e.g. for a small dataset you want fully cached locally), pass `dataset_kwargs={"streaming": False}`.

---

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `dataset_name` | `str` | — | Dataset name on the Hugging Face Hub (e.g. `"squad"`). |
| `split` | `str` | — | Which split to stream (`"train"`, `"validation"`, etc.). |
| `content_columns` | `list[str]` | — | Columns joined into `Document.content`. Must be non-empty. |
| `metadata_columns` | `list[str] \| None` | `None` | Columns to copy into `Document.metadata`. |
| `content_separator` | `str` | `"\n"` | Separator used to join `content_columns` values. |
| `dataset_kwargs` | `dict \| None` | `None` | Forwarded to `datasets.load_dataset` (subset name, revision, token, etc.). |

---

## Document Metadata

| Key | Value |
|-----|-------|
| `row_index` | Zero-based row position within the split |
| *(metadata_columns)* | Any column listed in `metadata_columns` |

`Document.source` is set to `"{dataset_name}/{split}"`, and `Document.type` is `DocumentType.TEXT`.
