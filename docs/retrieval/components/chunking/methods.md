# Chunking: Built-in methods

Four chunkers ship under `railtracks.retrieval.chunking`. Pick one based on
your source format and whether you need offsets back.

---

## Summary

| Chunker | Best for | Offsets on `Chunk`? |
|---|---|---|
| `RecursiveCharacterChunker` | **Default choice.** General text and markdown bodies. | Yes (character spans) |
| `MarkdownHeaderChunker` | Markdown with `#` / `##` hierarchy; header context in metadata. | Yes (when body spans are known) |
| `SentenceChunker` | Sentence-window retrieval; overlap measured in *sentences*. | Yes |
| `FixedTokenChunker` | Hard token budget per chunk (e.g. matching embedder max). | No (see note) |

---

## `RecursiveCharacterChunker`

Recursively splits on an ordered list of separators (paragraphs → lines →
sentence-like breaks → words → characters), then merges fragments into
chunks of at most `chunk_size` units (characters by default, or whatever
`length_fn` measures), with `overlap` between adjacent chunks.

```python
--8<-- "docs/scripts/retrieval/chunking.py:recursive"
```

**When to use:** unstructured or lightly structured text where you don't
need heading-aware metadata. Pair with a token `length_fn` (a
`Tokenizer.count`) if you also want to budget by tokens while keeping
character offsets; that combination is what `FixedTokenChunker` gives up.

---

## `MarkdownHeaderChunker`

Splits markdown on heading lines matching configured `#` prefixes. Each
emitted chunk carries heading context in metadata (`headers`, `section`).
If `chunk_size` is set and a section body is too long, the body is split
further using a fallback splitter (defaults to a zero-overlap `RecursiveSplitter`).

```python
--8<-- "docs/scripts/retrieval/chunking.py:md"
```

**When to use:** markdown knowledge bases, READMEs, documentation sites -
anywhere section boundaries are meaningful for retrieval (a hit in
"Authentication > OAuth Setup" tells you more than a hit somewhere on
page 4).

---

## `SentenceChunker`

Detects sentence boundaries (default: regex on `.`/`!`/`?` + whitespace),
then groups **`chunk_size` consecutive sentences** with **`overlap`
sentences** shared between adjacent windows. Each chunk gets
`metadata["sentence_count"]`.

```python
--8<-- "docs/scripts/retrieval/chunking.py:sentence"
```

**When to use:** sentence-window expansion (retrieve narrow windows, then
fetch neighbouring sentences for context). Inject a custom `Splitter` if
the regex default is too crude for your language.

---

## `FixedTokenChunker`

Encodes the document once, slices the token list into windows of
`chunk_size` tokens with `overlap` tokens between windows, then decodes
each window back to text. Default tokenizer is tiktoken `cl100k_base`.

```python
--8<-- "docs/scripts/retrieval/chunking.py:fixed"
```

**When to use:** you need chunk sizes aligned to the embedder's hard token
limit.

!!! note "Offsets and token chunking"
    `FixedTokenChunker` currently leaves `Chunk.offsets` as `None` -
    character-accurate spans for tiktoken-style windows require extra
    tokenizer plumbing. If you need both token budgeting and offsets,
    prefer `RecursiveCharacterChunker` with a token `length_fn` until
    token offsets are wired up.

---

## Choosing a chunker

| Situation | Start with |
|---|---|
| Plain text, HTML-to-text, PDF extract, mixed prose | `RecursiveCharacterChunker` |
| Markdown with real heading structure | `MarkdownHeaderChunker` (optionally + `chunk_size`) |
| Sentence-aligned retrieval windows | `SentenceChunker` |
| Hard token budget per chunk | `FixedTokenChunker` |

---

## Custom chunkers

Subclass `Chunker`, implement `chunk(self, document)`, and **always** build
results via `_make_chunks` so invariants (`document_id`, dense `index`,
metadata, offsets) stay correct. Implement `Splitter` for reusable
`str → list[str]` logic if the same boundary detection shows up in more
than one chunker.

```python
--8<-- "docs/scripts/retrieval/chunking.py:custom"
```

---

## See also

- [Chunking overview](index.md): objects, layers, pipeline placement.
- [Ingestion components](../ingestion/index.md): upstream `Document` production.
- [Embeddings methods](../../embeddings/methods.md): picking an embedder
  whose token limit matches your chunk size.
