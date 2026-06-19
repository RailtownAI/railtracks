# Chunking: Built-in methods

Six chunkers ship under `railtracks.retrieval.chunking`. Pick one based on
your source format and whether you need offsets back.

---

## Summary

| Chunker | Best for | Offsets on `Chunk`? |
|---|---|---|
| `IdentityChunker` | No splitting; entire document as one chunk. Baseline and pass-through. | Yes (full-document span) |
| `RecursiveCharacterChunker` | **Default choice.** General text and markdown bodies. | Yes (character spans) |
| `MarkdownHeaderChunker` | Markdown with `#` / `##` hierarchy; header context in metadata. | Yes (when body spans are known) |
| `SentenceChunker` | Sentence-window retrieval; overlap measured in *sentences*. | Yes |
| `SemanticChunker` | Topic boundaries via embeddings; variable chunk size. | Yes (unit spans in source text) |
| `FixedTokenChunker` | Hard token budget per chunk (e.g. matching embedder max). | No (see note) |

---

## `IdentityChunker`

Emits the entire document as a single chunk. No splitting is performed.
``Chunk.offsets`` spans ``(0, len(document.content))`` so offset-based slicing
works correctly downstream, just like with every other chunker.

```python
--8<-- "docs/scripts/retrieval/chunking.py:identity"
```

**When to use:**

- Short documents that must never be split (e.g. individual FAQ entries,
  product descriptions, code snippets).
- Baseline experiments: compare retrieval quality against a splitting strategy
  with no other variables changed.
- Pipeline pass-through: adapting a loader's output to a ``Chunker``-based
  interface when the downstream expects chunks but splitting is undesirable.

**Offsets:** Yes. ``Chunk.offsets == (0, len(document.content))``.

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

## `SemanticChunker`

Splits a document into **units** (sentences by default via `RegexSentenceSplitter`), embeds each unit with an injected **`Embedding`** provider, and merges consecutive units wherever **cosine distance** between neighbor embeddings exceeds a **percentile-based** threshold. Chunk count and size adapt to the document rather than a fixed window.

```python
--8<-- "docs/scripts/retrieval/chunking.py:semantic"
```

```python
--8<-- "docs/scripts/retrieval/chunking.py:semantic_achunk"
```

| Parameter | Description |
|-----------|-------------|
| `embedder` | Required `Embedding` implementation. `chunk()` uses `embed()`; `achunk()` uses `aembed()`. |
| `sentence_splitter` | Optional `Splitter` for units. Defaults to `RegexSentenceSplitter`. |
| `threshold_percentile` | Percentile (0–100) of pairwise cosine distances in the document; distances **above** this value become breakpoints. Higher → fewer, larger chunks. Default `95.0`. |
| `combine_neighbors` | When `True`, each string sent to the embedder includes neighboring units for richer context. Chunk **text** and **offsets** still come from original unit spans in `document.content`. |
| `window` | Neighbor radius on each side when `combine_neighbors=True`. Default `1`. |

**Pipeline (high level):**

1. Split `document.content` into positioned units `(text, start, end)`.
2. Embed unit texts (or contextualized strings if `combine_neighbors=True`).
3. Compute paired cosine distance between each adjacent embedding pair.
4. Break after units where distance exceeds `numpy.percentile(distances, threshold_percentile)`.
5. Merge units between breakpoints; each chunk is `document.content[first_start:last_end]`.

**When to use:** long prose where **topic shifts** matter more than fixed character, token, or sentence counts, and you already run an embedder in the pipeline.

**Offsets:** Yes. For every chunk, `document.content[s:e] == chunk.content` where `(s, e) = chunk.offsets`, spanning from the first merged unit’s start through the last unit’s end (including whitespace between sentences, as in the source).

!!! note "Optional dependency"
    `SemanticChunker` depends on `scikit-learn` (and `numpy`). Install with `pip install 'railtracks[semantic]'` or include it via `pip install 'railtracks[retrieval]'`. Without the extra, importing the chunker fails at module load time.

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
| Short docs that must stay whole, or pipeline pass-through | `IdentityChunker` |
| Plain text, HTML-to-text, PDF extract, mixed prose | `RecursiveCharacterChunker` |
| Markdown with real heading structure | `MarkdownHeaderChunker` (optionally + `chunk_size`) |
| Sentence-aligned retrieval windows | `SentenceChunker` |
| Topic- or embedding-driven boundaries | `SemanticChunker` |
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

- [Chunking overview](base.md): objects, layers, pipeline placement.
- [Ingestion components](../ingestion/base.md): upstream `Document` production.
- [Embeddings methods](../embeddings/methods.md): picking an embedder
  whose token limit matches your chunk size.
