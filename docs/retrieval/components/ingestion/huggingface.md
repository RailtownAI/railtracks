# Hugging Face Datasets

`HuggingFaceDatasetLoader` streams rows from any [Hugging Face Hub](https://huggingface.co/datasets)
dataset and emits one [`Document`](index.md#the-document-object) per
row. Rows are fetched lazily — works on datasets that wouldn't fit in
memory.

```bash
pip install "railtracks[huggingface]"
```

```python
from railtracks.retrieval.loaders.huggingface_loader import HuggingFaceDatasetLoader
```

---

## Basic usage

```python
--8<-- "docs/scripts/ingestion_example.py:hf_basic"
```

**Always use `astream()` here.** `aload()` and `load()` collect the full
split into memory before returning — fine for tiny demo datasets, disastrous
for `ag_news` or anything Common Crawl–scale.

---

## Joining multiple columns into content

```python
--8<-- "docs/scripts/ingestion_example.py:hf_multi_column"
```

Many QA and retrieval datasets store "the text" across columns
(`question` + `context`, `title` + `body`). Pass them all to
`content_columns` and join with a separator the embedder will respect.

---

## Forwarding metadata columns

```python
--8<-- "docs/scripts/ingestion_example.py:hf_metadata_columns"
```

Columns in `metadata_columns` are copied into `Document.metadata` as-is —
handy for citation, filtering on dataset-provided labels, or stratified
evaluation. **Anything not in `content_columns` or `metadata_columns` is
dropped** — be explicit about what you want.

---

## Subsets, revisions, auth

```python
--8<-- "docs/scripts/ingestion_example.py:hf_kwargs"
```

`dataset_kwargs` is forwarded straight to `datasets.load_dataset` — use
it for subset selectors (`name=`), revisions, or anything else the
Datasets library accepts.

For gated datasets, set `HF_TOKEN` in your environment or pass
`dataset_kwargs={"token": "hf_xxxxxxx"}`.

!!! tip "Streaming is the default"
    Streaming mode is on by default. Disable it (e.g. for a small dataset
    you want fully cached locally) with `dataset_kwargs={"streaming": False}`.

---

## Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `dataset_name` | `str` | — | Dataset name on the Hugging Face Hub (e.g. `"squad"`). |
| `split` | `str` | — | Which split to stream (`"train"`, `"validation"`, etc.). |
| `content_columns` | `list[str]` | — | Columns joined into `Document.content`. Must be non-empty. |
| `metadata_columns` | `list[str] \| None` | `None` | Columns to copy into `Document.metadata`. |
| `content_separator` | `str` | `"\n"` | Separator used to join `content_columns` values. |
| `dataset_kwargs` | `dict \| None` | `None` | Forwarded to `datasets.load_dataset` (subset name, revision, token, etc.). |

---

## Document metadata

| Key | Value |
|---|---|
| `row_index` | Zero-based row position within the split |
| *(metadata_columns)* | Any column listed in `metadata_columns` |

`Document.source` is `"{dataset_name}/{split}"`. `Document.type` is
`DocumentType.TEXT`.
