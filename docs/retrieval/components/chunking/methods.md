# `SemanticChunker`

Splits a document into **units** (sentences by default via `RegexSentenceSplitter`), embeds each unit with an injected **`Embedding`** provider, and merges consecutive units wherever **cosine distance** between neighbor embeddings exceeds a **percentile-based** threshold. Chunk count and size adapt to the document rather than a fixed window.

```python
from railtracks.retrieval import Document
from railtracks.retrieval.chunking import SemanticChunker
from railtracks.retrieval.embedding import OpenAIEmbedding

doc = Document(content=long_text, type="text", source="article.txt")
chunks = SemanticChunker(
    embedder=OpenAIEmbedding(),
    threshold_percentile=95.0,
).chunk(doc)
```

```python
# Async pipelines: prefer achunk (calls embedder.aembed)
chunks = await SemanticChunker(embedder=OpenAIEmbedding()).achunk(doc)
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
    `SemanticChunker` depends on `scikit-learn` (and `numpy`). Install with `pip install 'railtracks[rag]'` or `uv add 'railtracks[rag]'`. Without the extra, importing the chunker fails at module load time.

---

