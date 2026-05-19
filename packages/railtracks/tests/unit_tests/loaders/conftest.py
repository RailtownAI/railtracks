"""Shared fixtures for storage loader unit tests."""

import sys
from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock

import pytest

from railtracks.vector_stores.chunking.base_chunker import Chunk


# ---------------------------------------------------------------------------
# S3 helpers
# ---------------------------------------------------------------------------


def make_s3_client(objects: dict[str, str], encoding: str = "utf-8") -> MagicMock:
    """Return a mock boto3 S3 client pre-loaded with *objects* (key → text)."""
    client = MagicMock()

    paginator = MagicMock()
    page_contents = [{"Key": k} for k in objects]
    paginator.paginate.return_value = [{"Contents": page_contents}]
    client.get_paginator.return_value = paginator

    def _get_object(Bucket: str, Key: str, **_: Any) -> dict[str, Any]:
        text = objects[Key]
        return {"Body": MagicMock(read=MagicMock(return_value=text.encode(encoding)))}

    client.get_object.side_effect = _get_object
    return client


@pytest.fixture
def s3_client_factory():
    """Factory fixture: call with a dict[key, text] to get a mock S3 client."""
    return make_s3_client


# ---------------------------------------------------------------------------
# Azure Blob helpers
# ---------------------------------------------------------------------------


def make_container_client(blobs: dict[str, str], encoding: str = "utf-8") -> MagicMock:
    """Return a mock ContainerClient pre-loaded with *blobs* (name → text)."""
    container_client = MagicMock()

    blob_items = []
    for name in blobs:
        item = MagicMock()
        item.name = name
        blob_items.append(item)
    container_client.list_blobs.return_value = blob_items

    def _get_blob_client(blob_name: str) -> MagicMock:
        blob_client = MagicMock()
        text = blobs.get(blob_name, "")
        blob_client.download_blob.return_value.readall.return_value = text.encode(encoding)
        return blob_client

    container_client.get_blob_client.side_effect = _get_blob_client
    return container_client


@pytest.fixture
def container_client_factory():
    """Factory fixture: call with a dict[name, text] to get a mock ContainerClient."""
    return make_container_client


@contextmanager
def patch_azure(container_client: MagicMock):
    """Context manager that patches both azure.storage.blob and azure.identity."""
    from unittest.mock import patch

    mock_storage = MagicMock()
    mock_storage.ContainerClient.return_value = container_client

    mock_identity = MagicMock()

    with patch.dict(
        sys.modules,
        {
            "azure.storage.blob": mock_storage,
            "azure.storage": MagicMock(blob=mock_storage),
            "azure": MagicMock(
                storage=MagicMock(blob=mock_storage),
                identity=mock_identity,
            ),
            "azure.identity": mock_identity,
        },
    ):
        yield mock_storage, mock_identity


@pytest.fixture
def azure_patch():
    """Fixture exposing the patch_azure context manager."""
    return patch_azure


# ---------------------------------------------------------------------------
# GCS helpers
# ---------------------------------------------------------------------------


def make_gcs_client(objects: dict[str, str], encoding: str = "utf-8") -> MagicMock:
    """Return a mock google.cloud.storage.Client pre-loaded with *objects* (name → text)."""
    client = MagicMock()

    # list_blobs returns an iterable of blob objects with .name
    blob_items = []
    for name in objects:
        item = MagicMock()
        item.name = name
        blob_items.append(item)
    client.list_blobs.return_value = blob_items

    # client.bucket(...).blob(name).download_as_bytes()
    def _bucket(bucket_name: str) -> MagicMock:
        bucket = MagicMock()

        def _blob(name: str) -> MagicMock:
            b = MagicMock()
            b.download_as_bytes.return_value = objects.get(name, "").encode(encoding)
            return b

        bucket.blob.side_effect = _blob
        return bucket

    client.bucket.side_effect = _bucket
    return client


@contextmanager
def patch_gcs(gcs_client: MagicMock):
    """Context manager that patches google.cloud.storage."""
    from unittest.mock import patch

    mock_storage = MagicMock()
    mock_storage.Client.return_value = gcs_client

    with patch.dict(
        sys.modules,
        {
            "google": MagicMock(cloud=MagicMock(storage=mock_storage)),
            "google.cloud": MagicMock(storage=mock_storage),
            "google.cloud.storage": mock_storage,
        },
    ):
        yield mock_storage


@pytest.fixture
def gcs_client_factory():
    """Factory fixture: call with a dict[name, text] to get a mock GCS client."""
    return make_gcs_client


@pytest.fixture
def gcs_patch():
    """Fixture exposing the patch_gcs context manager."""
    return patch_gcs


# ---------------------------------------------------------------------------
# SQL helpers  (real in-memory SQLite — no mocking needed)
# ---------------------------------------------------------------------------


def make_sqlite_engine(rows: list[dict[str, Any]], table: str = "documents") -> Any:
    """Create an in-memory SQLite engine pre-populated with *rows*.

    Uses ``StaticPool`` so the same underlying connection is reused across all
    threads — necessary for ``asyncio.to_thread`` calls in async loader tests.
    The table is created dynamically from the keys of the first row.
    All column values are stored as TEXT for simplicity.

    Returns the SQLAlchemy engine; pass it directly to SQLLoader via ``engine=``.
    """
    import sqlalchemy as sa
    from sqlalchemy.pool import StaticPool

    engine = sa.create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    if not rows:
        return engine

    columns = list(rows[0].keys())
    col_defs = ", ".join(f"{c} TEXT" for c in columns)
    with engine.begin() as conn:
        conn.execute(sa.text(f"CREATE TABLE IF NOT EXISTS {table} ({col_defs})"))  # noqa: S608
        for row in rows:
            placeholders = ", ".join(f":{c}" for c in columns)
            conn.execute(
                sa.text(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"),  # noqa: S608
                row,
            )
    return engine


@pytest.fixture
def sqlite_engine_factory():
    """Factory fixture: call with rows and optional table name to get a real SQLite engine."""
    return make_sqlite_engine
