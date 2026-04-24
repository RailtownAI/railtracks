# Chunking — Built-in Methods

This page lists the chunkers shipped under `railtracks.retrieval.chunking`, with imports, typical use cases, and important limitations.

---

## Summary table

| Chunker | Import | Best for | Offsets on `Chunk`? |
|---------|--------|----------|---------------------|
| `RecursiveCharacterChunker` | `from railtracks.retrieval.chunking import RecursiveCharacterChunker` | General text and markdown bodies; default choice | Yes (character spans) |
| `MarkdownHeaderChunker` | `from railtracks.retrieval.chunking import MarkdownHeaderChunker` | Markdown with `#` / `##` / … hierarchy; header context in metadata | Yes (when body spans are known) |
| `SentenceChunker` | `from railtracks.retrieval.chunking import SentenceChunker` | Sentence-window style chunks; overlap in *sentences* | Yes |
| `FixedTokenChunker` | `from railtracks.retrieval.chunking import FixedTokenChunker` | Fixed token windows (tiktoken by default) | No (see note below) |

Supporting types: `Chunker`, `Splitter`, `Tokenizer`, `TiktokenTokenizer`, `RecursiveSplitter`, `RegexSentenceSplitter`.

---

## `RecursiveCharacterChunker`

Recursively splits on an ordered list of separators (paragraphs, lines, sentence-like breaks, words, then characters), then merges fragments into chunks of at most `chunk_size` units (characters by default, or whatever `length_fn` measures), with `overlap` between adjacent chunks.

```python
from railtracks.retrieval import Document
from railtracks.retrieval.chunking import RecursiveCharacterChunker

doc = Document(content=long_text, type="text", source="doc.txt")
chunks = RecursiveCharacterChunker(
    chunk_size=800,
    overlap=100,
    separators=["\n\n", "\n", ". ", " ", ""],  # optional; sensible defaults exist
).chunk(doc)
```

**When to use:** unstructured or lightly structured text where you do not need heading-aware metadata.

---

## `MarkdownHeaderChunker`

Splits markdown on heading lines that match configured `#` prefixes (e.g. `#`, `##`, `###`). Each emitted chunk carries heading context in metadata (`headers`, `section`). If `chunk_size` is set and a section body is too long, the body is split further using a fallback splitter (by default a `RecursiveSplitter` with overlap `0`).

```python
from railtracks.retrieval import Document
from railtracks.retrieval.chunking import MarkdownHeaderChunker

doc = Document(content=md_text, type="markdown", source="guide.md")
chunks = MarkdownHeaderChunker(
    headers_to_split_on=["#", "##", "###"],  # optional
    chunk_size=1000,                          # optional; omit to never subdivide bodies
).chunk(doc)
```

**When to use:** markdown knowledge bases, READMEs, and docs where section boundaries matter for retrieval or UI.

---

## `SentenceChunker`

Detects sentence boundaries (default: regex on `.` / `!` / `?` followed by whitespace), then groups **`chunk_size` consecutive sentences** with **`overlap` sentences** shared between adjacent windows. Each chunk includes `metadata["sentence_count"]`.

```python
from railtracks.retrieval import Document
from railtracks.retrieval.chunking import SentenceChunker

doc = Document(content=text, type="text", source="article.txt")
chunks = SentenceChunker(chunk_size=5, overlap=1).chunk(doc)
```

**When to use:** you want retrieval units aligned to sentence runs (e.g. sentence-window expansion). You can inject a custom `Splitter` if you need stronger linguistic boundaries than the default regex.

---

## `FixedTokenChunker`

Encodes the full document once, slices token lists into windows of `chunk_size` tokens with `overlap` tokens between windows, then decodes each window back to text. Default tokenizer is tiktoken `cl100k_base` via `TiktokenTokenizer`.

```python
from railtracks.retrieval import Document
from railtracks.retrieval.chunking import FixedTokenChunker

doc = Document(content=text, type="text", source="blob.txt")
chunks = FixedTokenChunker(chunk_size=400, overlap=50).chunk(doc)
```

**When to use:** you need chunk sizes aligned to embedding model token limits.

!!! note "Offsets and token chunking"
    In the current release, `FixedTokenChunker` leaves `Chunk.offsets` as `None`. Character-accurate spans for tiktoken-style windows require extra tokenizer plumbing. Prefer `RecursiveCharacterChunker` with a token `length_fn` if you need both token budgeting and offsets until token offsets are supported.

---

## Choosing a chunker

| Situation | Suggested starting point |
|-----------|----------------------------|
| Plain text, HTML-to-text, PDF extract, mixed prose | `RecursiveCharacterChunker` |
| Markdown with clear heading structure | `MarkdownHeaderChunker` (optionally still tune `chunk_size`) |
| Sentence-aligned windows | `SentenceChunker` |
| Hard token budget per chunk | `FixedTokenChunker` |

---

## Custom chunkers

Subclass `Chunker`, implement `chunk(self, document)`, and build results only via **`_make_chunks`** so invariants (`document_id`, dense `index`, metadata, offsets) stay correct. Implement `Splitter` for reusable `str -> list[str]` logic if you split the same way in more than one chunker.

```python
from railtracks.retrieval import Document
from railtracks.retrieval.chunking import Chunker

class ParagraphChunker(Chunker):
    def chunk(self, document: Document):
        pieces = document.content.split("\n\n")
        return self._make_chunks(document, pieces)
```

---

## See also

- [Chunking overview](overview.md) — objects, layers, pipeline
- [Ingestion overview](../ingestion/overview.md) — upstream `Document` production
