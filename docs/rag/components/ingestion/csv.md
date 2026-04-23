# CSV

`CSVLoader` reads `.csv` files and converts each **row** into a [`Document`](overview.md#the-document-object). Column values can be selectively placed into the document's `content` or kept as `metadata`. No extra dependencies are required.

```python
from railtracks.retrieval.loaders import CSVLoader
```

---

## Basic Usage

```python
loader = CSVLoader("products.csv")
docs = loader.load()

doc = docs[0]
print(doc.content)   # "name: Widget\nprice: 9.99\ndescription: A small widget"
print(doc.type)      # "csv"
print(doc.source)    # "products.csv"
print(doc.metadata)  # {"row_index": 0}
```

By default, **all columns** are included in `content`, formatted as `column: value` pairs joined by newlines.

---

## Controlling Which Columns Become Content

Use `content_columns` to specify exactly which columns make up the document's searchable text. All other columns automatically become metadata.

```python
loader = CSVLoader(
    "products.csv",
    content_columns=["name", "description"],
)
docs = loader.load()

doc = docs[0]
print(doc.content)   # "name: Widget\ndescription: A small widget"
print(doc.metadata)  # {"price": "9.99", "row_index": 0}
```

---

## Ignoring Columns

Use `ignore_columns` to drop columns entirely — they won't appear in `content` or `metadata`:

```python
loader = CSVLoader(
    "products.csv",
    content_columns=["name", "description"],
    ignore_columns=["internal_id", "last_updated"],
)
```

---

## Custom Content Separator

By default, content-column values are joined with `"\n"`. Change this with `content_separator`:

```python
loader = CSVLoader(
    "products.csv",
    content_columns=["name", "description"],
    content_separator=" | ",
)
# content: "name: Widget | description: A small widget"
```

---

## Loading a Directory

Pass a directory path to load **all** `.csv` files recursively:

```python
loader = CSVLoader("data/")
docs = loader.load()  # one Document per row, across all CSV files
```

---

## Async Loading

```python
loader = CSVLoader("products.csv", content_columns=["name", "description"])
docs = await loader.aload()
```

---

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `file_path` | `str` | — | Path to a `.csv` file or directory |
| `content_columns` | `list[str] \| None` | `None` | Columns to include in `Document.content`. `None` uses all columns. |
| `ignore_columns` | `list[str] \| None` | `None` | Columns to drop entirely |
| `content_separator` | `str` | `"\n"` | String used to join content-column values |
| `encoding` | `str` | `"utf-8-sig"` | File encoding (BOM-aware by default) |

---

## Document Metadata

| Key | Value |
|-----|-------|
| `row_index` | Zero-based row number within the file |
| *(all other columns)* | Any column not in `content_columns` or `ignore_columns` |
