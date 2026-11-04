"""Shared fixtures for cloud loader unit tests."""

from __future__ import annotations

import sys
from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock

import pytest


def _as_bytes(body: str | bytes, encoding: str) -> bytes:
    return body if isinstance(body, bytes) else body.encode(encoding)


def make_pdf(*pages: str) -> bytes:
    """Build a minimal valid PDF with one line of Helvetica text per page."""
    count = len(pages)
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(count))
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {count} >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for i, text in enumerate(pages):
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {5 + 2 * i} 0 R >>".encode()
        )
        stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
        objects.append(
            b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream)
        )

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (number, body)
    xref_offset = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref_offset,
    )
    return bytes(out)


# ---------------------------------------------------------------------------
# S3 helpers
# ---------------------------------------------------------------------------


def make_s3_client(
    objects: dict[str, str | bytes], encoding: str = "utf-8"
) -> MagicMock:
    """Return a mock boto3 S3 client pre-loaded with *objects* (key -> text or bytes)."""
    client = MagicMock()

    paginator = MagicMock()
    page_contents = [{"Key": k} for k in objects]
    paginator.paginate.return_value = [{"Contents": page_contents}]
    client.get_paginator.return_value = paginator

    def _get_object(Bucket: str, Key: str, **_: Any) -> dict[str, Any]:  # noqa: N803
        body = _as_bytes(objects[Key], encoding)
        return {"Body": MagicMock(read=MagicMock(return_value=body))}

    client.get_object.side_effect = _get_object
    return client


# ---------------------------------------------------------------------------
# Azure Blob helpers
# ---------------------------------------------------------------------------


def make_container_client_for_loading(
    blobs: dict[str, str | bytes], encoding: str = "utf-8"
) -> MagicMock:
    """Mock ContainerClient pre-loaded with *blobs* (name -> text or bytes)."""
    container_client = MagicMock()
    blob_items = []
    for name in blobs:
        item = MagicMock()
        item.name = name
        blob_items.append(item)
    container_client.list_blobs.return_value = blob_items

    def _get_blob_client(blob_name: str) -> MagicMock:
        blob_client = MagicMock()
        blob_client.download_blob.return_value.readall.return_value = _as_bytes(
            blobs.get(blob_name, ""), encoding
        )
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
    objects: dict[str, str | bytes], encoding: str = "utf-8"
) -> MagicMock:
    """Mock google.cloud.storage.Client pre-loaded with *objects* (name -> text or bytes)."""
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
            b.download_as_bytes.return_value = _as_bytes(
                objects.get(name, ""), encoding
            )
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
