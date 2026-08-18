from typing import TYPE_CHECKING

from .key_value import (
    InMemoryKeyValueStore,
    KeyValueStore,
)
from .models import (
    Entity,
    RetrievedStoreEntry,
    StoreEntry,
    StoreQuery,
    StoreScope,
)
from .protocol import Store
from .vector import VectorStore

if TYPE_CHECKING:
    from .vector.backends import (
        ChromaBackend,
        ChromaCloudBackend,
        DistanceMetric,
        PgvectorBackend,
    )
    from .vector.backends import (
        InMemoryBackend as InMemoryVectorBackend,
    )

__all__ = [
    "ChromaBackend",
    "ChromaCloudBackend",
    "DistanceMetric",
    "Entity",
    "InMemoryKeyValueStore",
    "InMemoryVectorBackend",
    "KeyValueStore",
    "PgvectorBackend",
    "RetrievedStoreEntry",
    "Store",
    "StoreEntry",
    "StoreQuery",
    "StoreScope",
    "VectorStore",
]


def __getattr__(name: str):
    if name == "ChromaBackend":
        from .vector.backends import ChromaBackend

        return ChromaBackend
    elif name == "ChromaCloudBackend":
        from .vector.backends import ChromaCloudBackend

        return ChromaCloudBackend
    elif name == "DistanceMetric":
        from .vector.backends import DistanceMetric

        return DistanceMetric
    elif name == "PgvectorBackend":
        from .vector.backends import PgvectorBackend

        return PgvectorBackend
    elif name == "InMemoryVectorBackend":
        from .vector.backends import InMemoryBackend as InMemoryVectorBackend

        return InMemoryVectorBackend
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
