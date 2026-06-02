"""Unit tests for GCSLoader."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from railtracks.retrieval.models import Document

from .conftest import make_gcs_client_for_loading, patch_gcs

BUCKET = "my-gcs-bucket"


# ---------------------------------------------------------------------------
# GCSLoader
# ---------------------------------------------------------------------------


class TestGCSLoaderInit:
    def test_raises_import_error_when_package_missing(self) -> None:
        from railtracks.retrieval.loaders.cloud.gcs import GCSLoader

        with patch.dict(
            sys.modules, {"google.cloud.storage": None, "google.cloud": None}
        ):
            with pytest.raises(ImportError, match="google-cloud-storage"):
                GCSLoader(BUCKET)

    def test_import_error_mentions_extra(self) -> None:
        from railtracks.retrieval.loaders.cloud.gcs import GCSLoader

        with patch.dict(
            sys.modules, {"google.cloud.storage": None, "google.cloud": None}
        ):
            with pytest.raises(ImportError, match="railtracks\\[gcp\\]"):
                GCSLoader(BUCKET)

    def test_explicit_credentials_forwarded_to_client(self) -> None:
        from railtracks.retrieval.loaders.cloud.gcs import GCSLoader

        fake_creds = MagicMock()
        gcs_client = make_gcs_client_for_loading({})
        with patch_gcs(gcs_client) as mock_storage:
            GCSLoader(BUCKET, credentials=fake_creds)
            mock_storage.Client.assert_called_once_with(
                project=None, credentials=fake_creds
            )

    def test_project_forwarded_to_client(self) -> None:
        from railtracks.retrieval.loaders.cloud.gcs import GCSLoader

        gcs_client = make_gcs_client_for_loading({})
        with patch_gcs(gcs_client) as mock_storage:
            GCSLoader(BUCKET, project="my-project")
            mock_storage.Client.assert_called_once_with(
                project="my-project", credentials=None
            )


class TestGCSLoaderKeys:
    def test_returns_document_for_each_key(self) -> None:
        from railtracks.retrieval.loaders.cloud.gcs import GCSLoader

        objects = {"doc1.txt": "hello", "doc2.txt": "world"}
        gcs_client = make_gcs_client_for_loading(objects)
        with patch_gcs(gcs_client):
            loader = GCSLoader(BUCKET, keys=list(objects.keys()))

        docs = loader.load()
        assert len(docs) == 2
        assert all(isinstance(d, Document) for d in docs)

    def test_document_source_is_full_uri(self) -> None:
        from railtracks.retrieval.loaders.cloud.gcs import GCSLoader

        gcs_client = make_gcs_client_for_loading({"file.txt": "data"})
        with patch_gcs(gcs_client):
            loader = GCSLoader(BUCKET, keys=["file.txt"])

        (doc,) = loader.load()
        assert doc.source == f"gs://{BUCKET}/file.txt"
        assert doc.metadata["bucket"] == BUCKET
        assert doc.metadata["name"] == "file.txt"


class TestGCSLoaderList:
    def test_load_returns_all_objects(self) -> None:
        from railtracks.retrieval.loaders.cloud.gcs import GCSLoader

        objects = {"a.txt": "aaa", "b.txt": "bbb", "c.txt": "ccc"}
        gcs_client = make_gcs_client_for_loading(objects)
        with patch_gcs(gcs_client):
            loader = GCSLoader(BUCKET)

        docs = loader.load()
        assert len(docs) == 3
        assert {d.content for d in docs} == {"aaa", "bbb", "ccc"}

    def test_prefix_passed_to_list_blobs(self) -> None:
        from railtracks.retrieval.loaders.cloud.gcs import GCSLoader

        gcs_client = make_gcs_client_for_loading({"docs/a.txt": "aaa"})
        with patch_gcs(gcs_client):
            loader = GCSLoader(BUCKET, prefix="docs/")

        loader.load()
        gcs_client.list_blobs.assert_called_once_with(BUCKET, prefix="docs/")

    def test_no_prefix_omits_prefix_kwarg(self) -> None:
        from railtracks.retrieval.loaders.cloud.gcs import GCSLoader

        gcs_client = make_gcs_client_for_loading({"a.txt": "aaa"})
        with patch_gcs(gcs_client):
            loader = GCSLoader(BUCKET)

        loader.load()
        gcs_client.list_blobs.assert_called_once_with(BUCKET)


@pytest.mark.asyncio
class TestGCSLoaderAsync:
    async def test_aload(self) -> None:
        from railtracks.retrieval.loaders.cloud.gcs import GCSLoader

        gcs_client = make_gcs_client_for_loading({"file.txt": "hello"})
        with patch_gcs(gcs_client):
            loader = GCSLoader(BUCKET, keys=["file.txt"])

        docs = await loader.aload()
        assert len(docs) == 1
        assert docs[0].content == "hello"
