"""
Vector-Store package entry-point.

from vector_store import create_store, InMemoryVectorStore
"""

from .factory import create_store
from .in_memory import InMemoryVectorStore

__all__ = [
    "create_store",
    "InMemoryVectorStore",
]
