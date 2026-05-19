"""
Cloud storage loader examples for use in documentation via --8<-- includes.

These snippets assume the relevant extras are installed:
    pip install railtracks[aws]          # for S3Loader
    pip install railtracks[azure-blob]   # for AzureBlobLoader
"""

# ---------------------------------------------------------------------------
# Shared setup used across sections
# ---------------------------------------------------------------------------
# --8<-- [start:shared_embedding]
from railtracks.rag.embedding_service import EmbeddingService

embedding_function = EmbeddingService().embed
# --8<-- [end:shared_embedding]


# ===========================================================================
# AWS S3
# ===========================================================================

# --8<-- [start:s3_basic]
from railtracks.loaders import S3Loader

loader = S3Loader("my-bucket", region_name="us-east-1")

# Load every object in the bucket
chunks = loader.load()

for chunk in chunks:
    print(chunk.metadata["source"], "→", chunk.content[:80])
# --8<-- [end:s3_basic]


# --8<-- [start:s3_prefix]
from railtracks.loaders import S3Loader

loader = S3Loader("my-bucket", region_name="us-east-1")

# Load only objects under the "knowledge-base/" prefix
chunks = loader.load(prefix="knowledge-base/")
# --8<-- [end:s3_prefix]


# --8<-- [start:s3_load_keys]
from railtracks.loaders import S3Loader

loader = S3Loader("my-bucket")

# Load a specific set of objects by key
chunks = loader.load_keys([
    "policy.txt",
    "faq.txt",
    "onboarding/welcome.txt",
])
# --8<-- [end:s3_load_keys]


# --8<-- [start:s3_explicit_creds]
from railtracks.loaders import S3Loader

loader = S3Loader(
    "my-bucket",
    aws_access_key_id="AKIA...",
    aws_secret_access_key="...",
    region_name="eu-west-1",
)
chunks = loader.load()
# --8<-- [end:s3_explicit_creds]


# --8<-- [start:s3_minio]
from railtracks.loaders import S3Loader

# Works with any S3-compatible service (MinIO, LocalStack, Ceph …)
loader = S3Loader(
    "my-bucket",
    endpoint_url="http://localhost:9000",
    aws_access_key_id="minioadmin",
    aws_secret_access_key="minioadmin",
)
chunks = loader.load()
# --8<-- [end:s3_minio]


# --8<-- [start:s3_async]
import asyncio
from railtracks.loaders import S3Loader

async def load_s3_documents():
    loader = S3Loader("my-bucket", region_name="us-east-1")

    # Both methods have async equivalents
    all_chunks = await loader.aload(prefix="docs/")
    specific_chunks = await loader.aload_keys(["readme.txt", "faq.txt"])
    return all_chunks + specific_chunks

chunks = asyncio.run(load_s3_documents())
# --8<-- [end:s3_async]


# ===========================================================================
# Azure Blob Storage
# ===========================================================================

# --8<-- [start:azure_basic]
from railtracks.loaders import AzureBlobLoader

# DefaultAzureCredential resolves credentials automatically
# (env vars, managed identity, Azure CLI, …)
loader = AzureBlobLoader(
    "https://myaccount.blob.core.windows.net",
    "my-container",
)

chunks = loader.load()

for chunk in chunks:
    print(chunk.metadata["source"], "→", chunk.content[:80])
# --8<-- [end:azure_basic]


# --8<-- [start:azure_prefix]
from railtracks.loaders import AzureBlobLoader

loader = AzureBlobLoader(
    "https://myaccount.blob.core.windows.net",
    "my-container",
)

# Load only blobs whose names begin with "reports/2025/"
chunks = loader.load(prefix="reports/2025/")
# --8<-- [end:azure_prefix]


# --8<-- [start:azure_load_keys]
from railtracks.loaders import AzureBlobLoader

loader = AzureBlobLoader(
    "https://myaccount.blob.core.windows.net",
    "my-container",
)

chunks = loader.load_keys([
    "policy.txt",
    "faq.txt",
    "onboarding/welcome.txt",
])
# --8<-- [end:azure_load_keys]


# --8<-- [start:azure_sas]
from azure.core.credentials import AzureSasCredential
from railtracks.loaders import AzureBlobLoader

loader = AzureBlobLoader(
    "https://myaccount.blob.core.windows.net",
    "my-container",
    credential=AzureSasCredential("<your-sas-token>"),
)
chunks = loader.load()
# --8<-- [end:azure_sas]


# --8<-- [start:azure_managed_identity]
from azure.identity import ManagedIdentityCredential
from railtracks.loaders import AzureBlobLoader

# Pin to a specific user-assigned managed identity via its client ID
loader = AzureBlobLoader(
    "https://myaccount.blob.core.windows.net",
    "my-container",
    credential=ManagedIdentityCredential(client_id="<client-id>"),
)
chunks = loader.load()
# --8<-- [end:azure_managed_identity]


# --8<-- [start:azure_async]
import asyncio
from railtracks.loaders import AzureBlobLoader

async def load_azure_documents():
    loader = AzureBlobLoader(
        "https://myaccount.blob.core.windows.net",
        "my-container",
    )

    all_chunks   = await loader.aload(prefix="reports/")
    named_chunks = await loader.aload_keys(["readme.txt", "faq.txt"])
    return all_chunks + named_chunks

chunks = asyncio.run(load_azure_documents())
# --8<-- [end:azure_async]


# ===========================================================================
# Feeding loaded chunks into a RAG pipeline
# ===========================================================================

# --8<-- [start:pipeline_s3_to_rag]
import railtracks as rt
from railtracks.loaders import S3Loader
from railtracks.vector_stores import ChromaVectorStore
from railtracks.rag.embedding_service import EmbeddingService

# 1. Load documents from S3
loader = S3Loader("my-knowledge-bucket", region_name="us-east-1")
chunks = loader.load(prefix="docs/")

# 2. Create a vector store and embed the chunks
embedding_fn = EmbeddingService().embed
store = ChromaVectorStore("knowledge-base", embedding_function=embedding_fn)
store.upsert(chunks)

# 3. Expose retrieval as an agent tool
@rt.function_node
def search_knowledge_base(query: str) -> str:
    """Search the internal knowledge base for relevant information."""
    results = store.search(query, top_k=5)
    return "\n\n".join(r.content for r in results)

# 4. Build the agent
agent = rt.agent_node(
    name="KnowledgeAgent",
    llm=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You are a helpful assistant. Use the knowledge base to answer questions.",
    tool_nodes=[search_knowledge_base],
)

flow = rt.Flow("knowledge-flow", entry_point=agent)
response = flow.invoke("What is our remote work policy?")
# --8<-- [end:pipeline_s3_to_rag]


# ===========================================================================
# Google Cloud Storage
# ===========================================================================

# --8<-- [start:gcs_basic]
from railtracks.loaders import GCSLoader

# Application Default Credentials resolve automatically
# (GOOGLE_APPLICATION_CREDENTIALS, gcloud auth, Workload Identity …)
loader = GCSLoader("my-bucket", project="my-gcp-project")

chunks = loader.load()

for chunk in chunks:
    print(chunk.metadata["source"], "→", chunk.content[:80])
# --8<-- [end:gcs_basic]


# --8<-- [start:gcs_prefix]
from railtracks.loaders import GCSLoader

loader = GCSLoader("my-bucket")
chunks = loader.load(prefix="knowledge-base/")
# --8<-- [end:gcs_prefix]


# --8<-- [start:gcs_load_keys]
from railtracks.loaders import GCSLoader

loader = GCSLoader("my-bucket")
chunks = loader.load_keys([
    "policy.txt",
    "faq.txt",
    "onboarding/welcome.txt",
])
# --8<-- [end:gcs_load_keys]


# --8<-- [start:gcs_service_account]
from google.oauth2 import service_account
from railtracks.loaders import GCSLoader

credentials = service_account.Credentials.from_service_account_file(
    "/path/to/service-account.json",
    scopes=["https://www.googleapis.com/auth/cloud-platform"],
)
loader = GCSLoader("my-bucket", credentials=credentials)
chunks = loader.load()
# --8<-- [end:gcs_service_account]


# --8<-- [start:gcs_async]
import asyncio
from railtracks.loaders import GCSLoader

async def load_gcs_documents():
    loader = GCSLoader("my-bucket", project="my-gcp-project")
    all_chunks   = await loader.aload(prefix="docs/")
    named_chunks = await loader.aload_keys(["readme.txt", "faq.txt"])
    return all_chunks + named_chunks

chunks = asyncio.run(load_gcs_documents())
# --8<-- [end:gcs_async]


# --8<-- [start:pipeline_gcs_to_rag]
import railtracks as rt
from railtracks.loaders import GCSLoader
from railtracks.vector_stores import ChromaVectorStore
from railtracks.rag.embedding_service import EmbeddingService

loader = GCSLoader("my-knowledge-bucket", project="my-gcp-project")
chunks = loader.load(prefix="docs/")

embedding_fn = EmbeddingService().embed
store = ChromaVectorStore("knowledge-base", embedding_function=embedding_fn)
store.upsert(chunks)

@rt.function_node
def search_knowledge_base(query: str) -> str:
    """Search the internal knowledge base for relevant information."""
    results = store.search(query, top_k=5)
    return "\n\n".join(r.content for r in results)

agent = rt.agent_node(
    name="KnowledgeAgent",
    llm=rt.llm.OpenAILLM("gpt-4o"),
    system_message="Answer questions using the knowledge base.",
    tool_nodes=[search_knowledge_base],
)

flow = rt.Flow("knowledge-flow", entry_point=agent)
response = flow.invoke("What is our remote work policy?")
# --8<-- [end:pipeline_gcs_to_rag]


# ===========================================================================
# SQL / Relational Database
# ===========================================================================

# --8<-- [start:sql_basic_postgres]
from railtracks.loaders import SQLLoader

loader = SQLLoader(
    "postgresql+psycopg2://user:pass@db.example.com:5432/mydb",
    table_or_query="documents",
    content_column="body",
    metadata_columns=["title", "author", "created_at"],
    id_column="id",
)
chunks = loader.load()

for chunk in chunks:
    print(chunk.metadata["title"], "→", chunk.content[:80])
# --8<-- [end:sql_basic_postgres]


# --8<-- [start:sql_supabase]
import os
from railtracks.loaders import SQLLoader

# Supabase exposes a standard PostgreSQL connection string
loader = SQLLoader(
    os.environ["SUPABASE_DB_URL"],  # postgresql+psycopg2://...
    table_or_query="knowledge_base",
    content_column="content",
    metadata_columns=["title", "category", "updated_at"],
    id_column="id",
    document_column="title",
)
chunks = loader.load()
# --8<-- [end:sql_supabase]


# --8<-- [start:sql_raw_query]
from railtracks.loaders import SQLLoader

loader = SQLLoader(
    "postgresql+psycopg2://user:pass@host/db",
    table_or_query=(
        "SELECT id, title, body "
        "FROM articles "
        "WHERE published = true AND category = 'policy'"
    ),
    content_column="body",
    id_column="id",
    document_column="title",
)
chunks = loader.load()
# --8<-- [end:sql_raw_query]


# --8<-- [start:sql_load_keys]
from railtracks.loaders import SQLLoader

loader = SQLLoader(
    "postgresql+psycopg2://user:pass@host/db",
    table_or_query="documents",
    content_column="body",
    id_column="id",
)
# Fetch only specific rows by their id column value
chunks = loader.load_keys(["doc-001", "doc-002", "doc-003"])
# --8<-- [end:sql_load_keys]


# --8<-- [start:sql_existing_engine]
import sqlalchemy as sa
from railtracks.loaders import SQLLoader

# Reuse an engine you already have configured (custom pool, SSL, etc.)
engine = sa.create_engine(
    "postgresql+psycopg2://user:pass@host/db",
    pool_size=5,
    max_overflow=10,
)
loader = SQLLoader(
    "",                    # ignored when engine= is provided
    table_or_query="documents",
    content_column="body",
    engine=engine,
)
chunks = loader.load()
# --8<-- [end:sql_existing_engine]


# --8<-- [start:sql_async]
import asyncio
from railtracks.loaders import SQLLoader

async def load_sql_documents():
    loader = SQLLoader(
        "postgresql+psycopg2://user:pass@host/db",
        table_or_query="documents",
        content_column="body",
        id_column="id",
    )
    all_chunks      = await loader.aload()
    specific_chunks = await loader.aload_keys(["doc-001", "doc-002"])
    return all_chunks

chunks = asyncio.run(load_sql_documents())
# --8<-- [end:sql_async]


# --8<-- [start:pipeline_sql_to_rag]
import railtracks as rt
from railtracks.loaders import SQLLoader
from railtracks.vector_stores import ChromaVectorStore
from railtracks.rag.embedding_service import EmbeddingService

loader = SQLLoader(
    "postgresql+psycopg2://user:pass@db.example.com/mydb",
    table_or_query="knowledge_base",
    content_column="content",
    metadata_columns=["title", "category"],
    id_column="id",
)
chunks = loader.load()

embedding_fn = EmbeddingService().embed
store = ChromaVectorStore("sql-knowledge", embedding_function=embedding_fn)
store.upsert(chunks)

@rt.function_node
def search_database(query: str) -> str:
    """Search the knowledge base for information relevant to the query."""
    results = store.search(query, top_k=5)
    return "\n\n".join(r.content for r in results)

agent = rt.agent_node(
    name="DatabaseAgent",
    llm=rt.llm.OpenAILLM("gpt-4o"),
    system_message="Answer questions using only information from the database.",
    tool_nodes=[search_database],
)

flow = rt.Flow("db-knowledge-flow", entry_point=agent)
response = flow.invoke("What is our refund policy?")
# --8<-- [end:pipeline_sql_to_rag]


# --8<-- [start:pipeline_azure_to_rag]
import railtracks as rt
from railtracks.loaders import AzureBlobLoader
from railtracks.vector_stores import ChromaVectorStore
from railtracks.rag.embedding_service import EmbeddingService

# 1. Load documents from Azure Blob Storage
loader = AzureBlobLoader(
    "https://myaccount.blob.core.windows.net",
    "company-docs",
)
chunks = loader.load(prefix="hr/")

# 2. Build a vector store
embedding_fn = EmbeddingService().embed
store = ChromaVectorStore("hr-docs", embedding_function=embedding_fn)
store.upsert(chunks)

# 3. Expose retrieval as a tool
@rt.function_node
def search_hr_docs(query: str) -> str:
    """Search HR documentation for policies and procedures."""
    results = store.search(query, top_k=5)
    return "\n\n".join(r.content for r in results)

# 4. Build the agent
agent = rt.agent_node(
    name="HRAgent",
    llm=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You are an HR assistant. Answer questions based on company policies.",
    tool_nodes=[search_hr_docs],
)

flow = rt.Flow("hr-flow", entry_point=agent)
response = flow.invoke("How many vacation days do I get?")
# --8<-- [end:pipeline_azure_to_rag]
