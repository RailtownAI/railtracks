"""
Cloud storage loader examples for use in documentation via --8<-- includes.

These snippets assume the relevant extras are installed:
    pip install railtracks[aws]          # for S3Loader
    pip install railtracks[azure-blob]   # for AzureBlobLoader
    pip install railtracks[gcp]          # for GCSLoader
    pip install railtracks[sql]          # for SQLLoader
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
from railtracks.retrieval.loaders import S3Loader

loader = S3Loader("my-bucket", region_name="us-east-1")

# Load every object in the bucket as Document instances
documents = loader.load()

for doc in documents:
    print(doc.source, "->", doc.content[:80])
# --8<-- [end:s3_basic]


# --8<-- [start:s3_prefix]
from railtracks.retrieval.loaders import S3Loader

# Load only objects under the "knowledge-base/" prefix
loader = S3Loader("my-bucket", prefix="knowledge-base/", region_name="us-east-1")
documents = loader.load()
# --8<-- [end:s3_prefix]


# --8<-- [start:s3_load_keys]
from railtracks.retrieval.loaders import S3Loader

# Load a specific set of objects by key
loader = S3Loader(
    "my-bucket",
    keys=["policy.txt", "faq.txt", "onboarding/welcome.txt"],
)
documents = loader.load()
# --8<-- [end:s3_load_keys]


# --8<-- [start:s3_explicit_creds]
from railtracks.retrieval.loaders import S3Loader

loader = S3Loader(
    "my-bucket",
    aws_access_key_id="AKIA...",
    aws_secret_access_key="...",
    region_name="eu-west-1",
)
documents = loader.load()
# --8<-- [end:s3_explicit_creds]


# --8<-- [start:s3_minio]
from railtracks.retrieval.loaders import S3Loader

# Works with any S3-compatible service (MinIO, LocalStack, Ceph ...)
loader = S3Loader(
    "my-bucket",
    endpoint_url="http://localhost:9000",
    aws_access_key_id="minioadmin",
    aws_secret_access_key="minioadmin",
)
documents = loader.load()
# --8<-- [end:s3_minio]


# --8<-- [start:s3_async]
import asyncio
from railtracks.retrieval.loaders import S3Loader

async def load_s3_documents():
    loader = S3Loader("my-bucket", prefix="docs/", region_name="us-east-1")

    # Stream documents as they download
    streamed = [doc async for doc in loader.astream()]

    # Or collect everything into a list
    all_docs = await loader.aload()
    return streamed + all_docs

documents = asyncio.run(load_s3_documents())
# --8<-- [end:s3_async]


# ===========================================================================
# Azure Blob Storage
# ===========================================================================

# --8<-- [start:azure_basic]
from railtracks.retrieval.loaders import AzureBlobLoader

# DefaultAzureCredential resolves credentials automatically
# (env vars, managed identity, Azure CLI, ...)
loader = AzureBlobLoader(
    "https://myaccount.blob.core.windows.net",
    "my-container",
)

documents = loader.load()

for doc in documents:
    print(doc.source, "->", doc.content[:80])
# --8<-- [end:azure_basic]


# --8<-- [start:azure_prefix]
from railtracks.retrieval.loaders import AzureBlobLoader

# Load only blobs whose names begin with "reports/2025/"
loader = AzureBlobLoader(
    "https://myaccount.blob.core.windows.net",
    "my-container",
    prefix="reports/2025/",
)
documents = loader.load()
# --8<-- [end:azure_prefix]


# --8<-- [start:azure_load_keys]
from railtracks.retrieval.loaders import AzureBlobLoader

loader = AzureBlobLoader(
    "https://myaccount.blob.core.windows.net",
    "my-container",
    keys=["policy.txt", "faq.txt", "onboarding/welcome.txt"],
)
documents = loader.load()
# --8<-- [end:azure_load_keys]


# --8<-- [start:azure_sas]
from azure.core.credentials import AzureSasCredential
from railtracks.retrieval.loaders import AzureBlobLoader

loader = AzureBlobLoader(
    "https://myaccount.blob.core.windows.net",
    "my-container",
    credential=AzureSasCredential("<your-sas-token>"),
)
documents = loader.load()
# --8<-- [end:azure_sas]


# --8<-- [start:azure_managed_identity]
from azure.identity import ManagedIdentityCredential
from railtracks.retrieval.loaders import AzureBlobLoader

# Pin to a specific user-assigned managed identity via its client ID
loader = AzureBlobLoader(
    "https://myaccount.blob.core.windows.net",
    "my-container",
    credential=ManagedIdentityCredential(client_id="<client-id>"),
)
documents = loader.load()
# --8<-- [end:azure_managed_identity]


# --8<-- [start:azure_async]
import asyncio
from railtracks.retrieval.loaders import AzureBlobLoader

async def load_azure_documents():
    loader = AzureBlobLoader(
        "https://myaccount.blob.core.windows.net",
        "my-container",
        prefix="reports/",
    )
    return await loader.aload()

documents = asyncio.run(load_azure_documents())
# --8<-- [end:azure_async]


# ===========================================================================
# Feeding loaded documents into a RAG pipeline
# ===========================================================================

# --8<-- [start:pipeline_s3_to_rag]
import railtracks as rt
from railtracks.retrieval.loaders import S3Loader
from railtracks.vector_stores import ChromaVectorStore
from railtracks.rag.embedding_service import EmbeddingService

# 1. Load documents from S3
loader = S3Loader("my-knowledge-bucket", prefix="docs/", region_name="us-east-1")
documents = loader.load()

# 2. Create a vector store and embed the documents
embedding_fn = EmbeddingService().embed
store = ChromaVectorStore("knowledge-base", embedding_function=embedding_fn)
store.upsert(documents)

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
from railtracks.retrieval.loaders import GCSLoader

# Application Default Credentials resolve automatically
# (GOOGLE_APPLICATION_CREDENTIALS, gcloud auth, Workload Identity ...)
loader = GCSLoader("my-bucket", project="my-gcp-project")

documents = loader.load()

for doc in documents:
    print(doc.source, "->", doc.content[:80])
# --8<-- [end:gcs_basic]


# --8<-- [start:gcs_prefix]
from railtracks.retrieval.loaders import GCSLoader

loader = GCSLoader("my-bucket", prefix="knowledge-base/")
documents = loader.load()
# --8<-- [end:gcs_prefix]


# --8<-- [start:gcs_load_keys]
from railtracks.retrieval.loaders import GCSLoader

loader = GCSLoader(
    "my-bucket",
    keys=["policy.txt", "faq.txt", "onboarding/welcome.txt"],
)
documents = loader.load()
# --8<-- [end:gcs_load_keys]


# --8<-- [start:gcs_service_account]
from google.oauth2 import service_account
from railtracks.retrieval.loaders import GCSLoader

credentials = service_account.Credentials.from_service_account_file(
    "/path/to/service-account.json",
    scopes=["https://www.googleapis.com/auth/cloud-platform"],
)
loader = GCSLoader("my-bucket", credentials=credentials)
documents = loader.load()
# --8<-- [end:gcs_service_account]


# --8<-- [start:gcs_async]
import asyncio
from railtracks.retrieval.loaders import GCSLoader

async def load_gcs_documents():
    loader = GCSLoader("my-bucket", project="my-gcp-project", prefix="docs/")
    return await loader.aload()

documents = asyncio.run(load_gcs_documents())
# --8<-- [end:gcs_async]


# --8<-- [start:pipeline_gcs_to_rag]
import railtracks as rt
from railtracks.retrieval.loaders import GCSLoader
from railtracks.vector_stores import ChromaVectorStore
from railtracks.rag.embedding_service import EmbeddingService

loader = GCSLoader("my-knowledge-bucket", project="my-gcp-project", prefix="docs/")
documents = loader.load()

embedding_fn = EmbeddingService().embed
store = ChromaVectorStore("knowledge-base", embedding_function=embedding_fn)
store.upsert(documents)

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
from railtracks.retrieval.loaders import SQLLoader

loader = SQLLoader(
    "postgresql+psycopg2://user:pass@db.example.com:5432/mydb",
    table_or_query="documents",
    content_column="body",
    metadata_columns=["title", "author", "created_at"],
    id_column="id",
)
documents = loader.load()

for doc in documents:
    print(doc.metadata["title"], "->", doc.content[:80])
# --8<-- [end:sql_basic_postgres]


# --8<-- [start:sql_supabase]
import os
from railtracks.retrieval.loaders import SQLLoader

# Supabase exposes a standard PostgreSQL connection string
loader = SQLLoader(
    os.environ["SUPABASE_DB_URL"],  # postgresql+psycopg2://...
    table_or_query="knowledge_base",
    content_column="content",
    metadata_columns=["title", "category", "updated_at"],
    id_column="id",
    source_column="title",
)
documents = loader.load()
# --8<-- [end:sql_supabase]


# --8<-- [start:sql_raw_query]
from railtracks.retrieval.loaders import SQLLoader

loader = SQLLoader(
    "postgresql+psycopg2://user:pass@host/db",
    table_or_query=(
        "SELECT id, title, body "
        "FROM articles "
        "WHERE published = true AND category = 'policy'"
    ),
    content_column="body",
    id_column="id",
    source_column="title",
)
documents = loader.load()
# --8<-- [end:sql_raw_query]


# --8<-- [start:sql_load_keys]
from railtracks.retrieval.loaders import SQLLoader

loader = SQLLoader(
    "postgresql+psycopg2://user:pass@host/db",
    table_or_query="documents",
    content_column="body",
    id_column="id",
    keys=["doc-001", "doc-002", "doc-003"],
)
documents = loader.load()
# --8<-- [end:sql_load_keys]


# --8<-- [start:sql_existing_engine]
import sqlalchemy as sa
from railtracks.retrieval.loaders import SQLLoader

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
documents = loader.load()
# --8<-- [end:sql_existing_engine]


# --8<-- [start:sql_async]
import asyncio
from railtracks.retrieval.loaders import SQLLoader

async def load_sql_documents():
    loader = SQLLoader(
        "postgresql+psycopg2://user:pass@host/db",
        table_or_query="documents",
        content_column="body",
        id_column="id",
    )
    return await loader.aload()

documents = asyncio.run(load_sql_documents())
# --8<-- [end:sql_async]


# --8<-- [start:pipeline_sql_to_rag]
import railtracks as rt
from railtracks.retrieval.loaders import SQLLoader
from railtracks.vector_stores import ChromaVectorStore
from railtracks.rag.embedding_service import EmbeddingService

loader = SQLLoader(
    "postgresql+psycopg2://user:pass@db.example.com/mydb",
    table_or_query="knowledge_base",
    content_column="content",
    metadata_columns=["title", "category"],
    id_column="id",
)
documents = loader.load()

embedding_fn = EmbeddingService().embed
store = ChromaVectorStore("sql-knowledge", embedding_function=embedding_fn)
store.upsert(documents)

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
from railtracks.retrieval.loaders import AzureBlobLoader
from railtracks.vector_stores import ChromaVectorStore
from railtracks.rag.embedding_service import EmbeddingService

# 1. Load documents from Azure Blob Storage
loader = AzureBlobLoader(
    "https://myaccount.blob.core.windows.net",
    "company-docs",
    prefix="hr/",
)
documents = loader.load()

# 2. Build a vector store
embedding_fn = EmbeddingService().embed
store = ChromaVectorStore("hr-docs", embedding_function=embedding_fn)
store.upsert(documents)

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
