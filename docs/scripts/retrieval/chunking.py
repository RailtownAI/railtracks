# --8<-- [start:quickstart]
from uuid import uuid4

from railtracks.retrieval import Document, DocumentType
from railtracks.retrieval.chunking import RecursiveCharacterChunker

doc = Document(
    content=(
        "This is a sample document that will be split into multiple overlapping chunks. "
        "Chunkers are useful for breaking up large texts for retrieval and question answering. "
        "Overlaps ensure context is preserved between chunks. "
        "Feel free to adjust chunk_size and overlap to see how chunking behaves."
    ),
    type=DocumentType.TEXT,
    id=uuid4(),
    source="example.txt",
    metadata={"author": "Test User"},
)

chunks = RecursiveCharacterChunker(chunk_size=60, overlap=15).chunk(doc)

for c in chunks:
    print(f"Chunk #{c.index}: offsets={c.offsets}, length={len(c.content)}")
    print(f"Content: {c.content!r}")
    print("-----")
# --8<-- [end:quickstart]

md_text = long_text = "..."

# --8<-- [start:recursive]
from railtracks.retrieval import Document
from railtracks.retrieval.chunking import RecursiveCharacterChunker

doc = Document(content=long_text, type=DocumentType.TEXT, source="doc.txt")
chunks = RecursiveCharacterChunker(
    chunk_size=800,
    overlap=100,
    separators=["\n\n", "\n", ". ", " ", ""],  # optional; sensible defaults exist
).chunk(doc)
# --8<-- [end:recursive]

# --8<-- [start:md]
from railtracks.retrieval import Document
from railtracks.retrieval.chunking import MarkdownHeaderChunker

doc = Document(content=md_text, type=DocumentType.MARKDOWN, source="guide.md")
chunks = MarkdownHeaderChunker(
    headers_to_split_on=["#", "##", "###"],  # optional
    chunk_size=1000,                          # optional; omit to never subdivide bodies
).chunk(doc)
# --8<-- [end:md]

# --8<-- [start:sentence]
from railtracks.retrieval import Document
from railtracks.retrieval.chunking import SentenceChunker

doc = Document(content=long_text, type=DocumentType.TEXT, source="article.txt")
chunks = SentenceChunker(chunk_size=5, overlap=1).chunk(doc)
# --8<-- [end:sentence]

# --8<-- [start:fixed]
from railtracks.retrieval import Document
from railtracks.retrieval.chunking import FixedTokenChunker

doc = Document(content=long_text, type=DocumentType.TEXT, source="blob.txt")
chunks = FixedTokenChunker(chunk_size=400, overlap=50).chunk(doc)
# --8<-- [end:fixed]

# --8<-- [start:custom]
from railtracks.retrieval import Document
from railtracks.retrieval.chunking import Chunker


class ParagraphChunker(Chunker):
    def chunk(self, document: Document):
        pieces = document.content.split("\n\n")
        return self._make_chunks(document, pieces)
# --8<-- [end:custom]