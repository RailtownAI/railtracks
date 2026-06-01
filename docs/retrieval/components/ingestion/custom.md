# Custom loaders

When the built-in loaders don't cover your source — a database table, an
internal API, a queue — write your own by subclassing `BaseDocumentLoader`.

---

## The contract

Subclass `BaseDocumentLoader` and implement `astream()`. It must be an
async generator that yields `Document` objects one at a time. `aload()`
and `load()` come for free — both derive from `astream()`.

```python
--8<-- "docs/scripts/ingestion_example.py:custom_loader"
```

Then use it like any other loader:

```python
--8<-- "docs/scripts/ingestion_example.py:custom_usage"
```

**Don't buffer the corpus.** Yield each `Document` as soon as it's ready.
The whole streaming pipeline depends on producers handing off work without
materializing everything first — buffer at your source and you break
back-pressure for every stage downstream.

---

## Wrapping a synchronous source

If your source only has a blocking API, use `asyncio.to_thread()` to push
the blocking call to a worker thread. The rest of the pipeline keeps
running on the event loop:

```python
--8<-- "docs/scripts/ingestion_example.py:custom_sync_wrap"
```

---

## Set `source` for free idempotency

Set `Document.source` to something stable — a path, a URL, a primary key.
The runtime hashes content and pairs it with `source` to skip re-ingest
of unchanged documents. Without a stable `source`, every run will look
"new" and you pay for embedding the same content repeatedly.

---

## JSON: a built-in custom example

`JSONLoader` is the built-in companion to `CSVLoader`. The root must be
an object or an array of objects; each object becomes one `Document`.

```python
--8<-- "docs/scripts/ingestion_example.py:json_loader"
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `file_path` | `str` | — | Path to a `.json` file or directory |
| `content_keys` | `list[str] \| "*"` | `"*"` | Keys whose values form `Document.content`. `"*"` serialises the whole object as JSON. |
| `ignore_keys` | `list[str] \| None` | `None` | Keys to drop entirely |
| `content_separator` | `str` | `"\n"` | Separator used to join content-key values |
| `encoding` | `str` | `"utf-8-sig"` | File encoding |
