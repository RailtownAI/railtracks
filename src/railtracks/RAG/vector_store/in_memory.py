from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from ..embedding_service import BaseEmbeddingService
from .base import AbstractVectorStore, Metric, SearchResult, VectorRecord
from .utils import distance, normalize_vector, uuid_str


class InMemoryVectorStore(AbstractVectorStore):
    """
    In-memory, pure-Python/NumPy implementation of the AbstractVectorStore.
    Stores feature vectors and metadata in standard dicts.

    Args:
        embedding_service: Optional embedding service for converting text to vectors.
        metric: Metric used for similarity (e.g., 'cosine', 'l2', 'dot').
        dim: Optionally restrict vectors to a fixed dimension for fast validation.
        normalize: Whether to normalize vectors (usually for cosine metric).

    Attributes:
        embedding_service: Used to embed texts into vectors, if provided.
        metric: Metric used for similarity or distance.
        _dim: Expected dimension of all vectors in the store.
        _normalize: Whether normalization is applied on add/search/update.
        _vectors: Maps record ids to vectors.
        _record: Maps record ids to VectorRecord objects containing metadata and text.
    """

    def __init__(
        self,
        *,
        embedding_service: Optional[BaseEmbeddingService] = None,
        metric: Union[str, Metric] = Metric.cosine,
        dim: Optional[int] = None,
        normalize: Optional[bool] = None,
    ):
        """
        Initialize an in-memory vector store.

        Args:
            embedding_service: Instance for text embedding.
            metric: Metric ('cosine', 'l2', or 'dot').
            dim: Expected vector dimensionality (autodetected on first add).
            normalize: Whether to normalize vectors (default: True for cosine).
        """
        self.embedding_service = embedding_service
        self.metric = Metric(metric)
        self._dim = dim
        # Default normalization: cosine --> True, others --> False (unless specified)
        self._normalize = (
            normalize if normalize is not None else (self.metric == Metric.cosine)
        )

        self._vectors: Dict[str, List[float]] = {}
        self._record: Dict[str, VectorRecord] = {}

    # ---------- CRUD ----------
    def add(
        self,
        texts_or_records: Sequence[Union[str, VectorRecord]],
        *,
        embed: bool = True,
        metadata: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> List[str]:
        """
        Add texts or full VectorRecord objects to the store.

        Args:
            texts_or_records: Sequence of either raw texts or VectorRecord objects.
            embed: If True, embed provided texts using embedding_service.
            metadata: Optionally, sequence of metadata dicts to pair with raw texts.

        Returns:
            List of string ids of added items.

        Raises:
            ValueError: If metadata list length mismatches or vector dimension mismatches.
            TypeError: If input items have unsupported type.
            RuntimeError: If embedding is required but embedding_service is not provided.
        """
        ids: List[str] = []

        if metadata and len(metadata) != len(texts_or_records):
            raise ValueError("metadata length must match texts/records length")

        for idx, item in enumerate(texts_or_records):
            if isinstance(item, VectorRecord):
                vec = item.vector
                record = item
                _id = item.id
            elif isinstance(item, str):
                if embed:
                    if not self.embedding_service:
                        raise RuntimeError("BaseEmbeddingService required but missing.")
                    vec = self.embedding_service.embed(item)
                else:
                    raise ValueError("Plain text given with embed=False")
                record = VectorRecord(id=uuid_str(), vector=vec, text=item)
                _id = uuid_str()
            else:
                raise TypeError("Unsupported type for add()")

            if self._dim is None:
                self._dim = len(vec)
            if len(vec) != self._dim:
                raise ValueError(f"Expected dim={self._dim}, got {len(vec)}")

            # Optionally normalize for cosine similarity
            if self._normalize:
                vec = normalize_vector(vec)

            self._vectors[_id] = vec
            self._record[_id] = record
            ids.append(_id)
        return ids

    def search(
        self,
        query: Union[str, List[float]],
        top_k: int = 5,
        *,
        embed: bool = False,
    ) -> List[SearchResult]:
        """
        Find the top-k most similar items to the query.

        Args:
            query: Input text (with embed=True) or vector.
            top_k: The number of results to return.
            embed: Whether to embed the query string (default True).

        Returns:
            List of SearchResult, ranked by similarity (ascending distance; descending score for dot/cos).

        Raises:
            ValueError: If wrong input type for embed setting, or not enough vectors.
            RuntimeError: If embedding required but missing service.
        """
        if isinstance(query, str):
            if not embed:
                raise ValueError("embed=False but query is text.")
            if not self.embedding_service:
                raise RuntimeError("BaseEmbeddingService required but missing.")
            q = self.embedding_service.embed(query)
        else:
            q = query
            if embed:
                raise ValueError("embed=True but raw vector supplied.")

        if self._normalize:
            q = normalize_vector(q)

        # Brute-force distance against all items
        scores = [
            (vid, distance(q, v, metric=self.metric.value))
            for vid, v in self._vectors.items()
        ]
        # Lower scores are better for all supported metrics
        scores.sort(key=lambda t: t[1])
        results = [
            SearchResult(
                score=score,
                record=self._record[vid],
            )
            for vid, score in scores[:top_k]
        ]
        return results

    def delete(self, ids: Sequence[str]) -> int:
        """
        Remove vectors and metadata entries by id.

        Args:
            ids: Record ids to delete.

        Returns:
            Number of successfully deleted entries.
        """
        removed = 0
        for _id in ids:
            if _id in self._vectors:
                self._vectors.pop(_id, None)
                self._record.pop(_id, None)
                removed += 1
        return removed

    def update(
        self,
        id: str,
        new_text_or_vector: Union[str, List[float]],
        *,
        embed: bool = True,
        **metadata,
    ) -> None:
        """
        Update an existing record's vector (from new text or vector) and/or metadata.

        Args:
            id: Id of the record to update.
            new_text_or_vector: The new text (embed=True) or raw vector (embed=False).
            embed: Whether to embed the given text (ignored if a vector is passed).
            **metadata: Arbitrary keyword arguments to update the item's metadata dict.

        Raises:
            KeyError: If the id to update does not exist.
            ValueError: If input types do not match embed flag.
            RuntimeError: If embedding required but missing service.
        """
        if id not in self._vectors:
            raise KeyError(id)

        if isinstance(new_text_or_vector, str):
            if not embed:
                raise ValueError("embed=False but given text.")
            if not self.embedding_service:
                raise RuntimeError("BaseEmbeddingService required but missing.")
            vec = self.embedding_service.embed(new_text_or_vector)

        else:
            vec = new_text_or_vector
            if embed:
                raise ValueError("embed=True but raw vector supplied.")

        if self._normalize:
            vec = normalize_vector(vec)
        record = VectorRecord(
            id=id,
            vector=vec,
            text=new_text_or_vector,
            metadata=metadata,
        )
        self._vectors[id] = vec
        self._record[id] = record

    # ---------- misc ----------

    def count(self) -> int:
        """
        Get the count of stored vectors.

        Returns:
            The number of records in the store.
        """
        return len(self._vectors)

    def persist(self, path: Union[str, Path, None] = None) -> None:
        """
        Persist the vector store to disk as a pickle file.

        Args:
            path: Folder or file path (if folder, 'in_memory_store.pkl' is used).
        """
        pickle_path = Path(path or ".")
        if pickle_path.is_dir() or not str(pickle_path).endswith(".pkl"):
            pickle_path /= "in_memory_store.pkl"
        with open(pickle_path, "wb") as f:
            pickle.dump(
                {
                    "metric": self.metric.value,
                    "dim": self._dim,
                    "normalize": self._normalize,
                    "vectors": self._vectors,
                    "record": self._record.json(),
                },
                f,
            )

    @classmethod
    def load(cls, path: Union[str, Path]):
        """
        Load a vector store from a pickle file.

        Args:
            path: Path to the pickle file.

        Returns:
            An `InMemoryVectorStore` instance reloaded from disk.
        """
        path = Path(path)
        with open(path, "rb") as f:
            data = pickle.load(f)
        store = cls(
            metric=data["metric"],
            dim=data["dim"],
            normalize=data["normalize"],
        )
        store._vectors = data["vectors"]
        store._record = {k: VectorRecord(**v) for k, v in data["record"].items()}
        return store
