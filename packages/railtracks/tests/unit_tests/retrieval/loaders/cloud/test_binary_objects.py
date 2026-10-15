"""Binary objects (PDFs and non-text files) across the S3, GCS and Azure Blob loaders."""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import Any
from unittest.mock import patch

import pytest
from railtracks.retrieval.loaders.base import BaseDocumentLoader
from railtracks.retrieval.models import DocumentType

from .conftest import (
    make_container_client_for_loading,
    make_gcs_client_for_loading,
    make_pdf,
    make_s3_client,
    patch_azure,
    patch_gcs,
)

BUCKET = "my-bucket"
ACCOUNT_URL = "https://acct.blob.core.windows.net"
CONTAINER = "docs"
PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\xff\xfe"

LoaderFactory = Callable[..., AbstractContextManager[BaseDocumentLoader]]


@contextmanager
def _s3_loader(
    objects: dict[str, str | bytes], **kwargs: Any
) -> Iterator[BaseDocumentLoader]:
    from railtracks.retrieval.loaders.cloud.s3 import S3Loader

    with patch("boto3.client", return_value=make_s3_client(objects)):
        yield S3Loader(BUCKET, keys=list(objects), **kwargs)


@contextmanager
def _gcs_loader(
    objects: dict[str, str | bytes], **kwargs: Any
) -> Iterator[BaseDocumentLoader]:
    with patch_gcs(make_gcs_client_for_loading(objects)):
        from railtracks.retrieval.loaders.cloud.gcs import GCSLoader

        yield GCSLoader(BUCKET, keys=list(objects), **kwargs)


@contextmanager
def _azure_loader(
    objects: dict[str, str | bytes], **kwargs: Any
) -> Iterator[BaseDocumentLoader]:
    with patch_azure(make_container_client_for_loading(objects)):
        from railtracks.retrieval.loaders.cloud.azure_blob import AzureBlobLoader

        yield AzureBlobLoader(ACCOUNT_URL, CONTAINER, keys=list(objects), **kwargs)


LOADERS = pytest.mark.parametrize(
    ("make_loader", "source_prefix", "provider_metadata"),
    [
        (_s3_loader, f"s3://{BUCKET}/", {"bucket": BUCKET}),
        (_gcs_loader, f"gs://{BUCKET}/", {"bucket": BUCKET}),
        (
            _azure_loader,
            f"{ACCOUNT_URL}/{CONTAINER}/",
            {"account_url": ACCOUNT_URL, "container": CONTAINER},
        ),
    ],
    ids=["s3", "gcs", "azure"],
)


@LOADERS
class TestPdfObjects:
    def test_pdf_yields_one_document_per_non_empty_page(
        self,
        make_loader: LoaderFactory,
        source_prefix: str,
        provider_metadata: dict[str, str],
    ) -> None:
        objects = {"report.pdf": make_pdf("First page", "", "Third page")}
        with make_loader(objects) as loader:
            docs = loader.load()

        assert [d.content for d in docs] == ["First page", "Third page"]
        assert all(d.type == DocumentType.PDF for d in docs)
        assert all(d.source == f"{source_prefix}report.pdf" for d in docs)
        assert [d.metadata["page"] for d in docs] == [1, 3]
        for doc in docs:
            assert doc.metadata["total_pages"] == 3
            assert doc.metadata["file_type"] == ".pdf"
            assert provider_metadata.items() <= doc.metadata.items()

    def test_document_strategy_yields_one_document(
        self,
        make_loader: LoaderFactory,
        source_prefix: str,
        provider_metadata: dict[str, str],
    ) -> None:
        objects = {"report.pdf": make_pdf("First page", "Second page")}
        with make_loader(objects, pdf_breakdown_strategy="document") as loader:
            (doc,) = loader.load()

        assert doc.content == "First page\n\nSecond page"
        assert doc.metadata["total_pages"] == 2
        assert "page" not in doc.metadata

    def test_invalid_breakdown_strategy_raises(
        self,
        make_loader: LoaderFactory,
        source_prefix: str,
        provider_metadata: dict[str, str],
    ) -> None:
        with pytest.raises(ValueError, match="pdf_breakdown_strategy"):
            with make_loader({}, pdf_breakdown_strategy="chapters"):
                pass

    def test_pdf_and_text_objects_keep_their_order(
        self,
        make_loader: LoaderFactory,
        source_prefix: str,
        provider_metadata: dict[str, str],
    ) -> None:
        objects: dict[str, str | bytes] = {
            "a.txt": "before",
            "b.pdf": make_pdf("middle"),
            "c.md": "# after",
        }
        with make_loader(objects) as loader:
            docs = loader.load()

        assert [d.content for d in docs] == ["before", "middle", "# after"]
        assert [d.type for d in docs] == [
            DocumentType.TEXT,
            DocumentType.PDF,
            DocumentType.MARKDOWN,
        ]


@LOADERS
class TestNonTextObjects:
    def test_non_text_object_is_skipped_with_warning(
        self,
        make_loader: LoaderFactory,
        source_prefix: str,
        provider_metadata: dict[str, str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        objects: dict[str, str | bytes] = {"logo.png": PNG_BYTES, "notes.txt": "hello"}
        with make_loader(objects) as loader, caplog.at_level(logging.WARNING):
            docs = loader.load()

        assert [d.content for d in docs] == ["hello"]
        warnings = [r.getMessage() for r in caplog.records]
        assert any(f"{source_prefix}logo.png" in m for m in warnings)


@LOADERS
class TestPdfExtraMissing:
    def test_text_objects_load_without_pypdf(
        self,
        make_loader: LoaderFactory,
        source_prefix: str,
        provider_metadata: dict[str, str],
    ) -> None:
        with patch.dict(sys.modules, {"railtracks.retrieval.loaders.pdf_loader": None}):
            with make_loader({"notes.txt": "hello"}) as loader:
                (doc,) = loader.load()

        assert doc.content == "hello"

    def test_pdf_without_pypdf_raises_install_hint(
        self,
        make_loader: LoaderFactory,
        source_prefix: str,
        provider_metadata: dict[str, str],
    ) -> None:
        with patch.dict(sys.modules, {"railtracks.retrieval.loaders.pdf_loader": None}):
            with make_loader({"report.pdf": make_pdf("text")}) as loader:
                with pytest.raises(ImportError, match=r"railtracks\[pdf\]"):
                    loader.load()
