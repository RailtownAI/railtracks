"""Shared fixtures and helpers for storage writer unit tests."""

import sys
from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# S3 helpers
# ---------------------------------------------------------------------------


def make_s3_client() -> MagicMock:
    """Return a mock boto3 S3 client that records put_object calls."""
    client = MagicMock()
    client.put_object.return_value = {}
    return client


@contextmanager
def patch_s3(s3_client: MagicMock):
    """Patch boto3.client so it returns *s3_client*."""
    import boto3
    from unittest.mock import patch

    with patch.object(boto3, "client", return_value=s3_client):
        yield s3_client


# ---------------------------------------------------------------------------
# Azure Blob helpers
# ---------------------------------------------------------------------------


def make_container_client() -> MagicMock:
    """Return a mock Azure ContainerClient that records upload_blob calls.

    Exposes ``container_client._written`` (name → bytes) and
    ``container_client._content_types`` (name → content_type str) so tests
    can verify what was written without chasing side_effect return values.
    """
    container_client = MagicMock()
    written: dict[str, bytes] = {}
    content_types: dict[str, str] = {}

    def _get_blob_client(name: str) -> MagicMock:
        blob_client = MagicMock()

        def _upload(data: bytes, *, overwrite: bool = False, content_settings=None) -> None:
            written[name] = data
            if content_settings is not None:
                # ContentSettings is a mock; grab content_type if set
                ct = getattr(content_settings, "content_type", None)
                if ct:
                    content_types[name] = ct

        blob_client.upload_blob.side_effect = _upload
        return blob_client

    container_client.get_blob_client.side_effect = _get_blob_client
    container_client._written = written
    container_client._content_types = content_types
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


def make_gcs_client() -> MagicMock:
    """Return a mock GCS client that records upload_from_string calls.

    Exposes ``client._written`` (name → bytes) and
    ``client._content_types`` (name → content_type str).
    """
    client = MagicMock()

    written: dict[str, bytes] = {}
    content_types: dict[str, str] = {}

    def _bucket(bucket_name: str) -> MagicMock:
        bucket = MagicMock()

        def _blob(name: str) -> MagicMock:
            b = MagicMock()
            b._name = name

            def _upload(data: bytes, content_type: str = "text/plain") -> None:
                written[name] = data
                content_types[name] = content_type

            b.upload_from_string.side_effect = _upload
            return b

        bucket.blob.side_effect = _blob
        return bucket

    client.bucket.side_effect = _bucket
    client._written = written
    client._content_types = content_types
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
# SQL helpers  (real in-memory SQLite)
# ---------------------------------------------------------------------------


def make_sqlite_engine(table: str = "documents", columns: list[str] | None = None) -> Any:
    """Create an empty in-memory SQLite engine with *columns*.

    Uses ``StaticPool`` so all threads share the same connection — required for
    ``asyncio.to_thread`` tests.  *columns* defaults to
    ``["id", "title", "body"]``.
    """
    import sqlalchemy as sa
    from sqlalchemy.pool import StaticPool

    if columns is None:
        columns = ["id", "title", "body"]

    engine = sa.create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    col_defs = ", ".join(f"{c} TEXT" for c in columns)
    with engine.begin() as conn:
        conn.execute(sa.text(f"CREATE TABLE {table} ({col_defs})"))  # noqa: S608
    return engine


def read_all_rows(engine: Any, table: str = "documents") -> list[dict[str, Any]]:
    """Read every row from *table* and return as a list of dicts."""
    import sqlalchemy as sa

    with engine.connect() as conn:
        result = conn.execute(sa.text(f"SELECT * FROM {table}"))  # noqa: S608
        return [dict(row._mapping) for row in result]


@pytest.fixture
def sqlite_engine():
    return make_sqlite_engine()


@pytest.fixture
def sqlite_engine_factory():
    return make_sqlite_engine
