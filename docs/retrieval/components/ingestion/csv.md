# CSV

`CSVLoader` reads `.csv` files and emits **one [`Document`](index.md#the-document-object)
per row**. Column values can go into `content` (searchable text) or
`metadata` (filterable, not embedded). No extra dependencies.

```python
from railtracks.retrieval.loaders import CSVLoader
```

---

## Basic usage

```python
--8<-- "docs/scripts/ingestion_example.py:csv_basic"
```

With no column config, **every column ends up in `content`** as
`column: value` lines. That's rarely what you want — IDs, timestamps, and
foreign keys add noise to the embedding without improving retrieval. Use
`content_columns` to be explicit.

---

## Selecting content columns

```python
--8<-- "docs/scripts/ingestion_example.py:csv_content_columns"
```

Columns *not* in `content_columns` automatically become metadata. That's
the right default — keep numeric IDs, prices, timestamps, and category
fields filterable but out of the embedding.

---

## Dropping columns entirely

```python
--8<-- "docs/scripts/ingestion_example.py:csv_ignore_columns"
```

Use `ignore_columns` for fields you don't want anywhere — internal IDs,
PII, audit timestamps that would only add noise to filters.

---

## Custom content separator

```python
--8<-- "docs/scripts/ingestion_example.py:csv_separator"
```

`"\n"` is fine for most cases — embedders handle newlines naturally. Use
`" | "` or `". "` when you want shorter chunks at the same token count.

---

## Loading a directory

```python
--8<-- "docs/scripts/ingestion_example.py:csv_directory"
```

Walks recursively. One Document per row, across every `.csv` under the
directory.

---

## Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `file_path` | `str` | — | Path to a `.csv` file or directory |
| `content_columns` | `list[str] \| None` | `None` | Columns joined into `Document.content`. `None` uses all columns. |
| `ignore_columns` | `list[str] \| None` | `None` | Columns to drop entirely (not in content, not in metadata) |
| `content_separator` | `str` | `"\n"` | String used to join content-column values |
| `encoding` | `str` | `"utf-8-sig"` | File encoding (BOM-aware by default) |

---

## Document metadata

| Key | Value |
|---|---|
| `row_index` | Zero-based row number within the file |
| *(all other columns)* | Any column not in `content_columns` or `ignore_columns` |
