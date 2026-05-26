"""
Cloud storage writer examples for use in documentation via --8<-- includes.

These snippets assume the relevant extras are installed:
    pip install railtracks[aws]          # for S3Writer
    pip install railtracks[azure-blob]   # for AzureBlobWriter
    pip install railtracks[gcp]          # for GCSWriter
    pip install railtracks[sql]          # for SQLWriter
"""

# ===========================================================================
# AWS S3
# ===========================================================================

# --8<-- [start:s3_write_basic]
from railtracks.integrations.writers import S3Writer

writer = S3Writer("my-bucket", region_name="us-east-1")

# Write raw text at an explicit key
uri = writer.write_key("reports/summary.txt", "Today's executive summary ...")
print(uri)  # s3://my-bucket/reports/summary.txt

# Write a list of Document objects -- key is derived from document.source / id
uris = writer.write(documents, prefix="generated/")
# --8<-- [end:s3_write_basic]


# --8<-- [start:s3_write_key_fn]
from railtracks.integrations.writers import S3Writer

# Use a custom function to derive the storage key from each document
writer = S3Writer(
    "my-bucket",
    key_fn=lambda doc: f"{doc.metadata.get('category', 'misc')}/{doc.id}.txt",
)
uris = writer.write(documents)
# --8<-- [end:s3_write_key_fn]


# --8<-- [start:s3_write_explicit_creds]
from railtracks.integrations.writers import S3Writer

writer = S3Writer(
    "my-bucket",
    aws_access_key_id="AKIA...",
    aws_secret_access_key="...",
    region_name="eu-west-1",
    content_type="application/json",
)
uri = writer.write_key("data/result.json", '{"status": "ok"}')
# --8<-- [end:s3_write_explicit_creds]


# --8<-- [start:s3_write_async]
import asyncio
from railtracks.integrations.writers import S3Writer

async def write_s3_documents():
    writer = S3Writer("my-bucket", region_name="us-east-1")

    # Write a batch of documents asynchronously
    uris = await writer.awrite(documents, prefix="output/")

    # Write a single object asynchronously
    uri = await writer.awrite_key("output/summary.txt", "Summary text ...")
    return uris

asyncio.run(write_s3_documents())
# --8<-- [end:s3_write_async]


# ===========================================================================
# Azure Blob Storage
# ===========================================================================

# --8<-- [start:azure_write_basic]
from railtracks.integrations.writers import AzureBlobWriter

# DefaultAzureCredential resolves credentials automatically
writer = AzureBlobWriter(
    "https://myaccount.blob.core.windows.net",
    "my-container",
)

# Write raw text at an explicit blob name
uri = writer.write_key("reports/summary.txt", "Today's executive summary ...")
print(uri)  # https://myaccount.blob.core.windows.net/my-container/reports/summary.txt

# Write a list of Document objects
uris = writer.write(documents, prefix="generated/")
# --8<-- [end:azure_write_basic]


# --8<-- [start:azure_write_sas]
from azure.core.credentials import AzureSasCredential
from railtracks.integrations.writers import AzureBlobWriter

writer = AzureBlobWriter(
    "https://myaccount.blob.core.windows.net",
    "my-container",
    credential=AzureSasCredential("<your-sas-token>"),
)
uris = writer.write(documents)
# --8<-- [end:azure_write_sas]


# --8<-- [start:azure_write_async]
import asyncio
from railtracks.integrations.writers import AzureBlobWriter

async def write_azure_documents():
    writer = AzureBlobWriter(
        "https://myaccount.blob.core.windows.net",
        "my-container",
    )
    uris = await writer.awrite(documents, prefix="output/")
    uri  = await writer.awrite_key("output/summary.txt", "Summary ...")
    return uris

asyncio.run(write_azure_documents())
# --8<-- [end:azure_write_async]


# ===========================================================================
# Google Cloud Storage
# ===========================================================================

# --8<-- [start:gcs_write_basic]
from railtracks.integrations.writers import GCSWriter

# Application Default Credentials resolve automatically
writer = GCSWriter("my-bucket", project="my-gcp-project")

# Write raw text at an explicit object name
uri = writer.write_key("reports/summary.txt", "Today's executive summary ...")
print(uri)  # gs://my-bucket/reports/summary.txt

# Write a list of Document objects
uris = writer.write(documents, prefix="generated/")
# --8<-- [end:gcs_write_basic]


# --8<-- [start:gcs_write_service_account]
from google.oauth2 import service_account
from railtracks.integrations.writers import GCSWriter

credentials = service_account.Credentials.from_service_account_file(
    "/path/to/service-account.json",
    scopes=["https://www.googleapis.com/auth/cloud-platform"],
)
writer = GCSWriter("my-bucket", credentials=credentials)
uris = writer.write(documents)
# --8<-- [end:gcs_write_service_account]


# --8<-- [start:gcs_write_async]
import asyncio
from railtracks.integrations.writers import GCSWriter

async def write_gcs_documents():
    writer = GCSWriter("my-bucket", project="my-gcp-project")
    uris = await writer.awrite(documents, prefix="output/")
    uri  = await writer.awrite_key("output/summary.txt", "Summary ...")
    return uris

asyncio.run(write_gcs_documents())
# --8<-- [end:gcs_write_async]


# ===========================================================================
# SQL / Relational Database
# ===========================================================================

# --8<-- [start:sql_write_basic]
from railtracks.integrations.writers import SQLWriter

writer = SQLWriter(
    "postgresql+psycopg2://user:pass@db.example.com:5432/mydb",
    table="documents",
    content_column="body",
    id_column="id",
    key_fn=lambda d: d.source,   # write a meaningful id, not an auto UUID
    metadata_columns=["title", "category"],
)

# Write (upsert) a list of Document objects
uris = writer.write(documents)
# Returns: ["sql://documents/<id>", ...]

# Write raw content at an explicit id
uri = writer.write_key("doc-42", "Revised policy text ...")
# Returns: "sql://documents/doc-42"
# --8<-- [end:sql_write_basic]


# --8<-- [start:sql_write_supabase]
import os
from railtracks.integrations.writers import SQLWriter

writer = SQLWriter(
    os.environ["SUPABASE_DB_URL"],  # postgresql+psycopg2://...
    table="knowledge_base",
    content_column="content",
    id_column="id",
    key_fn=lambda d: d.source,
    source_column="title",
    metadata_columns=["category", "updated_at"],
)
uris = writer.write(documents)
# --8<-- [end:sql_write_supabase]


# --8<-- [start:sql_write_modes]
from railtracks.integrations.writers import SQLWriter

# Default: "upsert" -- existing rows with the same id are replaced
writer = SQLWriter(
    "postgresql+psycopg2://user:pass@host/db",
    table="documents",
    content_column="body",
    id_column="id",
    mode="upsert",   # safe to call repeatedly
)
writer.write(documents)

# "insert" mode -- rows are appended without conflict handling
append_writer = SQLWriter(
    "postgresql+psycopg2://user:pass@host/db",
    table="audit_log",
    content_column="message",
    mode="insert",
)
append_writer.write(documents)
# --8<-- [end:sql_write_modes]


# --8<-- [start:sql_write_existing_engine]
import sqlalchemy as sa
from railtracks.integrations.writers import SQLWriter

engine = sa.create_engine(
    "postgresql+psycopg2://user:pass@host/db",
    pool_size=5,
    max_overflow=10,
)
writer = SQLWriter(
    "",                    # ignored when engine= is provided
    table="documents",
    content_column="body",
    id_column="id",
    engine=engine,
)
uris = writer.write(documents)
# --8<-- [end:sql_write_existing_engine]


# --8<-- [start:sql_write_async]
import asyncio
from railtracks.integrations.writers import SQLWriter

async def write_sql_documents():
    writer = SQLWriter(
        "postgresql+psycopg2://user:pass@host/db",
        table="documents",
        content_column="body",
        id_column="id",
        key_fn=lambda d: d.source,
    )
    uris = await writer.awrite(documents)
    uri  = await writer.awrite_key("doc-99", "New content ...")
    return uris

asyncio.run(write_sql_documents())
# --8<-- [end:sql_write_async]


# ===========================================================================
# Load -> Generate -> Write back (end-to-end)
# ===========================================================================

# --8<-- [start:pipeline_generate_and_write]
import railtracks as rt
from railtracks.retrieval.loaders import S3Loader
from railtracks.integrations.writers import S3Writer
from railtracks.retrieval.models import Document, DocumentType

# 1. Load source documents
loader = S3Loader("source-bucket", prefix="raw/", region_name="us-east-1")
source_documents = loader.load()

# 2. Run an agent to generate a summary for each document
summariser = rt.agent_node(
    name="Summariser",
    llm=rt.llm.OpenAILLM("gpt-4o-mini"),
    system_message="Summarise the provided document in 2-3 sentences.",
)

writer = S3Writer("output-bucket", region_name="us-east-1")

for doc in source_documents:
    result = summariser.invoke(doc.content)
    summary = Document(
        content=result.content,
        type=DocumentType.TEXT,
        source=doc.source,
        metadata={"original_source": doc.source, "type": "summary"},
    )
    uri = writer.write_key(f"summaries/{doc.id}.txt", summary.content)
    print(f"Saved summary -> {uri}")
# --8<-- [end:pipeline_generate_and_write]
