# Chunking — Built-in methods

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

Supporting types: `Chunker`, `Splitter`, `Tokenizer`, `TiktokenTokenizer`,
`RecursiveSplitter`, `RegexSentenceSplitter`.

**When in doubt, use `RecursiveCharacterChunker(800, 100)`.** It works for
~90% of corpora, gives you character offsets, and doesn't need a tokenizer.

---

## `RecursiveCharacterChunker`

Recursively splits on an ordered list of separators (paragraphs → lines →
sentence-like breaks → words → characters), then merges fragments into
chunks of at most `chunk_size` units (characters by default, or whatever
`length_fn` measures), with `overlap` between adjacent chunks.

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

**When to use:** unstructured or lightly structured text where you don't
need heading-aware metadata. Pair with a token `length_fn` (a
`Tokenizer.count`) if you also want to budget by tokens while keeping
character offsets — that combination is what `FixedTokenChunker` gives up.

---

## `MarkdownHeaderChunker`

Splits markdown on heading lines matching configured `#` prefixes. Each
emitted chunk carries heading context in metadata (`headers`, `section`).
If `chunk_size` is set and a section body is too long, the body is split
further using a fallback splitter (defaults to a zero-overlap `RecursiveSplitter`).

```python
from railtracks.retrieval import Document
from railtracks.retrieval.chunking import MarkdownHeaderChunker

doc = Document(content=md_text, type="markdown", source="guide.md")
chunks = MarkdownHeaderChunker(
    headers_to_split_on=["#", "##", "###"],  # optional
    chunk_size=1000,                          # optional; omit to never subdivide bodies
).chunk(doc)
```

**When to use:** markdown knowledge bases, READMEs, documentation sites —
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
from railtracks.retrieval import Document
from railtracks.retrieval.chunking import SentenceChunker

doc = Document(content=text, type="text", source="article.txt")
chunks = SentenceChunker(chunk_size=5, overlap=1).chunk(doc)
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
from railtracks.retrieval import Document
from railtracks.retrieval.chunking import FixedTokenChunker

doc = Document(content=text, type="text", source="blob.txt")
chunks = FixedTokenChunker(chunk_size=400, overlap=50).chunk(doc)
```

**When to use:** you need chunk sizes aligned to the embedder's hard token
limit. For OpenAI text-embedding-3 (8191 tokens), `chunk_size=400` with
`overlap=50` is a safe production starting point.

!!! note "Offsets and token chunking"
    `FixedTokenChunker` currently leaves `Chunk.offsets` as `None` —
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
from railtracks.retrieval import Document
from railtracks.retrieval.chunking import Chunker


class ParagraphChunker(Chunker):
    def chunk(self, document: Document):
        pieces = document.content.split("\n\n")
        return self._make_chunks(document, pieces)
```

---

## See also

- [Chunking overview](index.md) — objects, layers, pipeline placement.
- [Ingestion components](../ingestion/index.md) — upstream `Document` production.
- [Embeddings methods](../../embeddings/methods.md) — picking an embedder
  whose token limit matches your chunk size.
