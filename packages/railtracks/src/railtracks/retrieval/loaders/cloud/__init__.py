#   -------------------------------------------------------------
#   Copyright (c) Railtown AI. All rights reserved.
#   Licensed under the MIT License. See LICENSE in project root for information.
#   -------------------------------------------------------------
"""Cloud-storage and database loaders for Railtracks.

Each provider module exposes a ``*Loader`` (subclass of
:class:`~railtracks.retrieval.loaders.base.BaseDocumentLoader`) that yields
:class:`~railtracks.retrieval.models.Document` objects.

Provider-specific writers live separately under
:mod:`railtracks.integrations.writers` (the retrieval module is loading-only).
"""

from railtracks.retrieval.loaders.cloud.azure_blob import AzureBlobLoader
from railtracks.retrieval.loaders.cloud.gcs import GCSLoader
from railtracks.retrieval.loaders.cloud.s3 import S3Loader
from railtracks.retrieval.loaders.cloud.sql import SQLLoader

__all__ = [
    "AzureBlobLoader",
    "GCSLoader",
    "S3Loader",
    "SQLLoader",
]
