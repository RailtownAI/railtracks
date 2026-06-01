"""Ingestion examples used by docs/retrieval/ingestion.md and per-loader pages.

Each section is wrapped in `# --8<-- [start:name]` / `[end:name]` markers
so docs can pull individual snippets via mkdocs-material's snippets extension.
"""

# Top-level imports are intentionally minimal. Per-snippet imports live
# inside each section so optional dependencies don't break import-checks.
from railtracks.retrieval.loaders import BaseDocumentLoader  # noqa: E402

from railtracks.retrieval.loaders import TextLoader

async def base_example():
# --8<-- [start:base]
    loader = TextLoader("docs/")

    # Sync, returns list[Document]. Fine for tests, small corpora, scripts.
    docs = loader.load()

    # Async, collects all documents before returning. Same memory profile as load().
    docs = await loader.aload()

    # Async, yields one Document at a time. The only mode that streams.
    async for doc in loader.astream():
        print(doc.source, doc.type, len(doc.content))
# --8<-- [end:base]



# --8<-- [start:runtime_setup]
import asyncio

from railtracks.retrieval import RetrievalRuntime
from railtracks.retrieval.chunking import RecursiveCharacterChunker
from railtracks.retrieval.embedding import OpenAIEmbedding
from railtracks.retrieval.loaders import TextLoader
from railtracks.retrieval.stores import InMemoryVectorBackend, VectorStore


def build_runtime() -> RetrievalRuntime:
    return RetrievalRuntime(
        chunker=RecursiveCharacterChunker(chunk_size=800, overlap=100),
        embedder=OpenAIEmbedding(model="text-embedding-3-small"),
        store=VectorStore(InMemoryVectorBackend()),
    )
# --8<-- [end:runtime_setup]


# --8<-- [start:ingest_all]
async def main(runtime: RetrievalRuntime):
    # Drains the stream and returns an IngestionStats summary.
    stats = await runtime.ingest_all(TextLoader("./docs"))
    print(
        f"loaded={stats.documents_loaded} "
        f"chunks={stats.chunks_embedded} "
        f"skipped={stats.documents_skipped}"
    )
# --8<-- [end:ingest_all]


# --8<-- [start:streaming]
from railtracks.retrieval import (
    BatchIngested,
    DocumentFailed,
    DocumentSkipped,
    EmbeddingFailure,
    RetrievalRuntime,
)


async def stream(runtime: RetrievalRuntime, loader):
    async for event in runtime.ingest(loader):
        match event:
            case BatchIngested(document_id=did, embedded_chunks=ch, batch_index=i):
                print(f"  + doc={did} batch={i} chunks={len(ch)}")
            case EmbeddingFailure(errors=errs):
                print(f"  ! batch failed: {errs[0]}")
            case DocumentFailed(document_id=did):
                print(f"  ! doc {did} ended with failures")
            case DocumentSkipped(source=src):
                print(f"  ~ skipped (unchanged): {src}")
# --8<-- [end:streaming]


# --8<-- [start:reingest]
from railtracks.retrieval import Document, DocumentType

class SampleLoader(BaseDocumentLoader):
    
    doc = Document(content="...", type=DocumentType.TEXT, source="handbook.md")
    async def astream(self):
        yield self.doc

async def reingest(runtime: RetrievalRuntime):
    # Same Document.id → upsert. The runtime clears prior chunks for this
    # document after the first batch succeeds, then writes the new ones.
    # A full embedding failure leaves the prior version intact.
    await runtime.ingest_all(loader=SampleLoader())

    # Same source + identical content → skipped via SHA-256 content_hash lookup.
    # ingest() yields DocumentSkipped without calling the embedder.
    await runtime.ingest_all(loader=SampleLoader())
# --8<-- [end:reingest]


# --8<-- [start:scope_on_write]
from railtracks.retrieval.stores import StoreScope  # noqa: E402


async def multitenant_write():
    # One runtime, one store, one set of infrastructure. Scope is a
    # per-call parameter — not a constructor argument — because it's
    # request-level context, not runtime config.
    runtime = RetrievalRuntime(
        chunker=RecursiveCharacterChunker(chunk_size=800),
        embedder=OpenAIEmbedding(),
        store=VectorStore(InMemoryVectorBackend()),
    )

    await runtime.ingest_all(
        TextLoader("./alice_docs"), scope=StoreScope(labels={"user_id": "alice"})
    )
    await runtime.ingest_all(
        TextLoader("./bob_docs"), scope=StoreScope(labels={"user_id": "bob"})
    )

    # Reads pass scope the same way; nothing crosses tenants.
    await runtime.retrieve("favorite color", scope=StoreScope(labels={"user_id": "alice"}))
# --8<-- [end:scope_on_write]


# --8<-- [start:sanitizing]
import re

from railtracks.retrieval.loaders import SanitizingLoader, TextLoader


class EmailRedactor:
    """Implements the Sanitizer protocol: .sanitize(Document) -> Document.
    Stateful by design — real redactors hold compiled regexes, denylists,
    or an async client to a DLP service."""

    EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")

    def sanitize(self, document: Document) -> Document:
        document.content = self.EMAIL.sub("[REDACTED]", document.content)
        return document


# Wrap any loader. Sanitizer runs once per Document, before chunking.
loader = SanitizingLoader(TextLoader("./hr_docs"), sanitizer=EmailRedactor())
# --8<-- [end:sanitizing]


# --8<-- [start:on_ingest_hook]
import asyncio


def audit(event):
    # Sync hook — runs inline with the ingest stream. Keep it cheap:
    # logging, in-process counters, metrics .inc() calls.
    print(f"[audit] {type(event).__name__}: {event}")


def audit_async(event):
    # Slow or async work? Schedule it and return immediately so the
    # stream keeps moving. Errors surface on the task, not on ingest.
    asyncio.create_task(_send_to_audit_log(event))


async def _send_to_audit_log(event) -> None:
    # Stand-in for a real async client (asyncpg, aiohttp webhook, etc.).
    ...


def build_with_hook():
    return RetrievalRuntime(
        chunker=RecursiveCharacterChunker(chunk_size=800),
        embedder=OpenAIEmbedding(),
        store=VectorStore(InMemoryVectorBackend()),
        on_ingest=audit,
    )
# --8<-- [end:on_ingest_hook]


# --8<-- [start:max_tokens]
def build_with_token_guard():
    # Chunks above 8000 tokens are dropped pre-flight and surface as
    # EmbeddingFailure events rather than provider-side 400s. A default
    # TiktokenTokenizer is wired up automatically when max_tokens is set.
    return RetrievalRuntime(
        chunker=RecursiveCharacterChunker(chunk_size=2000),
        embedder=OpenAIEmbedding(model="text-embedding-3-small"),
        store=VectorStore(InMemoryVectorBackend()),
        max_tokens=8000,  # OpenAI's text-embedding-3 hard cap is 8191
    )
# --8<-- [end:max_tokens]


# ---------------------------------------------------------------------------
# Per-loader snippets (consumed by per-loader doc pages)
# ---------------------------------------------------------------------------


# --8<-- [start:text_single_file]
from railtracks.retrieval.loaders import TextLoader



loader = TextLoader("notes.txt")
docs = loader.load()

doc = docs[0]
print(doc.content)            # full file text
print(doc.type)               # "text" or "markdown"
print(doc.source)             # "notes.txt"
print(doc.metadata)           # {"file_type": ".txt", "encoding": "utf-8-sig"}
# --8<-- [end:text_single_file]


# --8<-- [start:text_directory]

# Recursively loads .txt and .md files, sorted by path.
docs = TextLoader("knowledge_base/").load()
print(len(docs))
print(docs[0].source)
# --8<-- [end:text_directory]


# --8<-- [start:text_encoding]
def text_encoding():
    # utf-8-sig (BOM-aware) is the default. Override per loader.
    docs = TextLoader("legacy_docs/", encoding="latin-1").load()
    print(docs[0].metadata["encoding"])  # "latin-1"
# --8<-- [end:text_encoding]


# --8<-- [start:text_async]
async def text_async():
    docs = await TextLoader("docs/").aload()                  # collect all at once
    async for doc in TextLoader("docs/").astream():           # one at a time
        print(doc.source, len(doc.content))
# --8<-- [end:text_async]


# --8<-- [start:csv_basic]
from railtracks.retrieval.loaders import CSVLoader



# Every row becomes a Document. By default, all columns end up in content.
docs = CSVLoader("products.csv").load()

doc = docs[0]
print(doc.content)   # "name: Widget\nprice: 9.99\ndescription: ..."
print(doc.type)      # "csv"
print(doc.metadata)  # {"row_index": 0}
# --8<-- [end:csv_basic]


# --8<-- [start:csv_content_columns]

# Columns in content_columns form the searchable text.
# Everything else automatically becomes metadata (filterable downstream).
loader = CSVLoader(
    "products.csv",
    content_columns=["name", "description"],
)
docs = loader.load()
print(docs[0].content)   # "name: Widget\ndescription: ..."
print(docs[0].metadata)  # {"price": "9.99", "row_index": 0}
# --8<-- [end:csv_content_columns]


# --8<-- [start:csv_ignore_columns]

# ignore_columns drops columns entirely — neither content nor metadata.
CSVLoader(
    "products.csv",
    content_columns=["name", "description"],
    ignore_columns=["internal_id", "last_updated"],
)
# --8<-- [end:csv_ignore_columns]


# --8<-- [start:csv_separator]

# Default content_separator is "\n". Change it for single-line records.
CSVLoader(
    "products.csv",
    content_columns=["name", "description"],
    content_separator=" | ",
)
# --8<-- [end:csv_separator]

# --8<-- [start:pdf_basic]

# Requires: pip install "railtracks[pdf]"
from railtracks.retrieval.loaders.pdf_loader import PyPDFLoader

docs = PyPDFLoader("report.pdf").load()
doc = docs[0]
print(doc.content)   # extracted text from page 1
print(doc.type)      # "pdf"
print(doc.metadata)  # {"page": 1, "total_pages": 42, "file_type": ".pdf"}
# --8<-- [end:pdf_basic]


# --8<-- [start:pdf_page_strategy]

from railtracks.retrieval.loaders.pdf_loader import PyPDFLoader

# One Document per page. Best for retrieval — keeps page numbers in
# metadata, which makes citations trivial.
docs = PyPDFLoader("report.pdf", breakdown_strategy="page").load()
print(len(docs))              # number of pages
print(docs[0].metadata)       # {"page": 1, "total_pages": 42, "file_type": ".pdf"}
# --8<-- [end:pdf_page_strategy]


# --8<-- [start:pdf_document_strategy]

from railtracks.retrieval.loaders.pdf_loader import PyPDFLoader

# Single Document. Pages joined with "\n\n". Use only when the whole PDF
# is small enough to chunk together or you want to apply custom splitting.
docs = PyPDFLoader("report.pdf", breakdown_strategy="document").load()
print(len(docs))        # always 1
# --8<-- [end:pdf_document_strategy]


# --8<-- [start:pdf_ocr_basic]

# Requires: pip install "railtracks[ocr]" + Tesseract on PATH.
from railtracks.retrieval.loaders.pdf_ocr_loader import PyPDFOCRLoader

docs = PyPDFOCRLoader("scanned_invoice.pdf").load()
doc = docs[0]
print(doc.content)         # OCR'd or pypdf-extracted text
print(doc.metadata["ocr"]) # True if OCR was used for this page
# --8<-- [end:pdf_ocr_basic]


# --8<-- [start:pdf_ocr_force]

from railtracks.retrieval.loaders.pdf_ocr_loader import PyPDFOCRLoader

# Skip the text-extraction fast path. Useful when pypdf returns a
# garbled or incomplete text layer that you'd rather re-OCR.
docs = PyPDFOCRLoader("messy_scan.pdf", force_ocr=True).load()
assert all(d.metadata["ocr"] for d in docs)
# --8<-- [end:pdf_ocr_force]


# --8<-- [start:pdf_ocr_document_strategy]

from railtracks.retrieval.loaders.pdf_ocr_loader import PyPDFOCRLoader

docs = PyPDFOCRLoader("report.pdf", breakdown_strategy="document").load()
print(docs[0].metadata)
    # {"total_pages": 42, "file_type": ".pdf", "ocr_pages": [3, 7, 8]}
# --8<-- [end:pdf_ocr_document_strategy]


# --8<-- [start:hf_basic]
async def hf_basic():
    # Requires: pip install "railtracks[huggingface]"
    from railtracks.retrieval.loaders.huggingface_loader import HuggingFaceDatasetLoader

    loader = HuggingFaceDatasetLoader(
        dataset_name="ag_news",
        split="test",
        content_columns=["text"],
    )
    # Rows are streamed; use astream() for anything larger than memory.
    async for doc in loader.astream():
        print(doc.content[:80])
        print(doc.source)    # "ag_news/test"
        print(doc.metadata)  # {"row_index": 0}
# --8<-- [end:hf_basic]


# --8<-- [start:hf_multi_column]

from railtracks.retrieval.loaders.huggingface_loader import HuggingFaceDatasetLoader

# Many datasets split "the text" across columns. Join them with
# content_separator instead of stitching things yourself downstream.
HuggingFaceDatasetLoader(
    dataset_name="squad",
    split="validation",
    content_columns=["question", "context"],
    content_separator="\n\n",
)
# --8<-- [end:hf_multi_column]


# --8<-- [start:hf_metadata_columns]

from railtracks.retrieval.loaders.huggingface_loader import HuggingFaceDatasetLoader

# metadata_columns are copied into Document.metadata for later filtering
# or citation. Anything not in content_columns or metadata_columns is dropped.
HuggingFaceDatasetLoader(
    dataset_name="squad",
    split="validation",
    content_columns=["question", "context"],
    metadata_columns=["title", "id"],
)
# --8<-- [end:hf_metadata_columns]


# --8<-- [start:hf_kwargs]

from railtracks.retrieval.loaders.huggingface_loader import HuggingFaceDatasetLoader

# dataset_kwargs is forwarded straight to datasets.load_dataset.
# Use it for subsets, revisions, gated-dataset tokens, or to disable streaming.
HuggingFaceDatasetLoader(
    dataset_name="ms_marco",
    split="validation",
    content_columns=["query", "passages"],
    dataset_kwargs={"name": "v2.1"},
)
# --8<-- [end:hf_kwargs]


# --8<-- [start:json_loader]

from railtracks.retrieval.loaders import JSONLoader

# Root must be an object or array of objects. content_keys selects which
# keys form the searchable text; ignore_keys drops keys entirely.
docs = JSONLoader(
    "articles.json",
    content_keys=["title", "body"],
    ignore_keys=["internal_id"],
).load()

print(docs[0].content)   # "title: Getting started\nbody: ..."
print(docs[0].metadata)  # {"author": "Alice", "index": 0}
# --8<-- [end:json_loader]


# --8<-- [start:custom_loader]
from collections.abc import AsyncGenerator

from railtracks.retrieval import Document, DocumentType  
from railtracks.retrieval.loaders import BaseDocumentLoader  


class MyDatabaseLoader(BaseDocumentLoader):
    """One Document per row of a database table."""

    def __init__(self, dsn: str, table: str) -> None:
        self._dsn = dsn
        self._table = table

    async def astream(self) -> AsyncGenerator[Document, None]:
        rows = await _async_fetch_rows(self._dsn, self._table)
        for row in rows:
            yield Document(
                content=row["body"],
                type=DocumentType.TEXT,
                source=f"{self._table}:{row['id']}",
                metadata={"author": row["author"], "created_at": row["created_at"]},
            )
# --8<-- [end:custom_loader]


# --8<-- [start:custom_usage]

loader = MyDatabaseLoader("postgresql://...", table="articles")
# Implementing astream() gets you load() and aload() for free.
loader.load()
# --8<-- [end:custom_usage]


# --8<-- [start:custom_sync_wrap]
class MySyncLoader(BaseDocumentLoader):
    """Wrap a blocking source without blocking the event loop."""

    async def astream(self) -> AsyncGenerator[Document, None]:
        rows = await asyncio.to_thread(_fetch_rows_sync)
        for row in rows:
            yield Document(content=row["text"], type=DocumentType.TEXT)
# --8<-- [end:custom_sync_wrap]


# Stubs so the file import-checks cleanly. Real code lives in user-land.
async def _async_fetch_rows(_dsn: str, _table: str) -> list[dict]:
    return []


def _fetch_rows_sync() -> list[dict]:
    return []
