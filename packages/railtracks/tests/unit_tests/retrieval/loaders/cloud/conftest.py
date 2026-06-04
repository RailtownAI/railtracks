"""Shared fixtures for cloud loader unit tests."""

from __future__ import annotations

import sys
from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# S3 helpers
# ---------------------------------------------------------------------------


def make_s3_client(objects: dict[str, str], encoding: str = "utf-8") -> MagicMock:
    """Return a mock boto3 S3 client pre-loaded with *objects* (key -> text)."""
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


# ---------------------------------------------------------------------------
# Azure Blob helpers
# ---------------------------------------------------------------------------


def make_container_client_for_loading(
    blobs: dict[str, str], encoding: str = "utf-8"
) -> MagicMock:
    """Mock ContainerClient pre-loaded with *blobs* (name -> text)."""
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


@contextmanager
def patch_azure(container_client: MagicMock):
    """Patch azure.storage.blob and azure.identity."""
    from unittest.mock import patch

    mock_storage = MagicMock()
    mock_storage.ContainerClient.return_value = container_client
    mock_storage.ContentSettings.return_value = MagicMock()

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


# ---------------------------------------------------------------------------
# GCS helpers
# ---------------------------------------------------------------------------


def make_gcs_client_for_loading(
    objects: dict[str, str], encoding: str = "utf-8"
) -> MagicMock:
    """Mock google.cloud.storage.Client pre-loaded with *objects*."""
    client = MagicMock()

    blob_items = []
    for name in objects:
        item = MagicMock()
        item.name = name
        blob_items.append(item)
    client.list_blobs.return_value = blob_items

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
    """Patch google.cloud.storage."""
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


# ---------------------------------------------------------------------------
# SQL helpers (real in-memory SQLite)
# ---------------------------------------------------------------------------


def make_sqlite_engine(
    rows: list[dict[str, Any]] | None = None,
    *,
    table: str = "documents",
    columns: list[str] | None = None,
) -> Any:
    """Create an in-memory SQLite engine.

    When *rows* is provided the table is created from the keys of the first row
    and populated with the given rows. When *rows* is ``None`` an empty table
    is created from *columns* (defaulting to ``["id", "title", "body"]``).

    Uses ``StaticPool`` so the same connection is reused across threads (needed
    for ``asyncio.to_thread`` calls in async loader tests).
    """
    import sqlalchemy as sa
    from sqlalchemy.pool import StaticPool

    engine = sa.create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    if rows:
        columns = list(rows[0].keys())
    elif columns is None:
        columns = ["id", "title", "body"]

    col_defs = ", ".join(f"{c} TEXT" for c in columns)
    with engine.begin() as conn:
        conn.execute(sa.text(f"CREATE TABLE {table} ({col_defs})"))  # noqa: S608
        for row in rows or []:
            placeholders = ", ".join(f":{c}" for c in columns)
            conn.execute(
                sa.text(
                    f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"  # noqa: S608
                ),
                row,
            )
    return engine


@pytest.fixture
def sqlite_engine():
    return make_sqlite_engine()


@pytest.fixture
def sqlite_engine_factory():
    return make_sqlite_engine
