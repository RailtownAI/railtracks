from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from ..embedding_service import BaseEmbeddingService
from .base import AbstractVectorStore, Metric, SearchEntry, SearchResult, VectorRecord
from .utils import distance, normalize_vector, uuid_str


class InMemoryVectorStore(AbstractVectorStore):
    """
    In-memory implementation of AbstractVectorStore.

    Stores vectors and records in Python dictionaries. Supports optional embedding
    of raw texts into vectors via an injected BaseEmbeddingService, multiple
    similarity metrics, normalization, basic CRUD, and persistence via pickle.

    Args:
        embedding_service: Optional embedding service for converting text to vectors.
        metric: Metric used for similarity (e.g., 'cosine', 'l2', 'dot').
        dim: Optionally restrict vectors to a fixed dimension for validation.
        normalize: Whether to normalize vectors (default True for cosine metric).

    Attributes:
        embedding_service: Used to embed texts into vectors, if provided.
        metric: Metric used for similarity/distance.
        _dim: Expected dimension of all vectors in the store.
        _normalize: Whether normalization is applied on add/search/update.
        _vectors: Maps record ids to vectors (List[float]).
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
            dim: Expected vector dimensionality (autodetected on first add if None).
            normalize: Whether to normalize vectors (default: True for cosine).
        """
        self.embedding_service = embedding_service

        # Normalize incoming metric to the Metric type (if patched in tests, still OK).
        self.metric = Metric(metric)

        # Determine default normalization robustly, even under patched Metric.
        if normalize is None:
            # Try to infer metric name from different potential representations.
            m_raw = metric  # preserve constructor arg
            if isinstance(m_raw, str):
                mname = m_raw.lower()
            else:
                # Metric-like: try to use .value, else fallback to its str()
                mname = str(getattr(m_raw, "value", str(m_raw))).lower()
            self._normalize = mname == "cosine"
        else:
            self._normalize = normalize

        self._dim = dim
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
        Add raw texts or prebuilt VectorRecord objects to the store.

        Args:
            texts_or_records: Sequence of either raw texts or VectorRecord objects.
            embed: If True, embed provided texts using embedding_service.
                   If False, texts are not allowed (must pass VectorRecord).
            metadata: Optional sequence of metadata dicts to attach/merge per item.

        Returns:
            List of string ids of added items.

        Raises:
            ValueError: If metadata length mismatches input length; if dimension mismatches;
                        or if plain text is given with embed=False.
            TypeError: If an input item has an unsupported type.
            RuntimeError: If embedding is required but embedding_service is not provided.
        """
        ids: List[str] = []

        if metadata is not None and len(metadata) != len(texts_or_records):
            raise ValueError("metadata length must match texts/records length")

        for idx, item in enumerate(texts_or_records):
            # Prepare initial values
            _id: str
            vec: List[float]
            rec_text: Optional[Union[str, List[float]]] = None
            rec_meta: Optional[Dict[str, Any]] = None

            if isinstance(item, VectorRecord):
                # Use provided id if present; otherwise generate a new one
                _id = getattr(item, "id", None) or uuid_str()
                vec = item.vector
                rec_text = item.text
                # Start from record's own metadata (if any)
                rec_meta = getattr(item, "metadata", None)
                # Merge per-item metadata if provided: test expects to attach metadata
                if metadata is not None and metadata[idx] is not None:
                    base_meta = rec_meta or {}
                    merged = dict(base_meta)
                    merged.update(metadata[idx])
                    rec_meta = merged
            elif isinstance(item, str):
                if not embed:
                    raise ValueError("Plain text given with embed=False")
                if not self.embedding_service:
                    raise RuntimeError("BaseEmbeddingService required but missing.")
                _id = uuid_str()
                rec_text = item
                vec = self.embedding_service.embed(item)
                rec_meta = metadata[idx] if (metadata is not None) else None
            else:
                raise TypeError("Unsupported type for add()")

            # Dimension checks and autodetection
            if self._dim is None:
                self._dim = len(vec)
            if len(vec) != self._dim:
                raise ValueError(f"Expected dim={self._dim}, got {len(vec)}")

            # Optional normalization
            stored_vec = normalize_vector(vec) if self._normalize else vec

            # Ensure the stored record mirrors the final id/vector/text/metadata
            record = VectorRecord(
                id=_id, vector=stored_vec, text=rec_text, metadata=rec_meta
            )

            # Persist
            self._vectors[_id] = stored_vec
            self._record[_id] = record
            ids.append(_id)

        return ids

    def search(
        self,
        query: Union[str, List[float]],
        top_k: int = 5,
        *,
        embed: bool = False,
    ) -> SearchResult:
        """
        Find the top-k most similar items to the query.

        Args:
            query: Input text (with embed=True) or vector.
            top_k: The number of results to return.
            embed: Whether to embed the query string (default False).

        Returns:
            A SearchResult object containing SearchEntry items, ranked by ascending
            distance (or equivalently, descending similarity depending on the metric).

        Raises:
            ValueError: If wrong input type for embed setting.
            RuntimeError: If embedding is required but missing service.
        """
        if isinstance(query, str):
            if not embed:
                raise ValueError("embed=False but query is text.")
            if not self.embedding_service:
                raise RuntimeError("BaseEmbeddingService required but missing.")
            q: List[float] = self.embedding_service.embed(query)
        else:
            # Query is a vector
            if embed:
                raise ValueError("embed=True but raw vector supplied.")
            q = query

        if self._normalize:
            q = normalize_vector(q)

        # Brute-force distance against all items
        scores = [
            (vid, distance(q, v, metric=self.metric.value))
            for vid, v in self._vectors.items()
        ]
        scores.sort(key=lambda t: t[1])  # lower is better

        results = SearchResult(
            SearchEntry(
                score=score,
                record=self._record[vid],
            )
            for vid, score in scores[: max(0, top_k)]
        )
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
            **metadata: Arbitrary keyword arguments to merge into the item's metadata.

        Raises:
            KeyError: If the id to update does not exist.
            ValueError: If input types do not match embed flag.
            RuntimeError: If embedding required but missing service.
        """
        if id not in self._vectors:
            raise KeyError(id)

        existing = self._record[id]

        if isinstance(new_text_or_vector, str):
            if not embed:
                raise ValueError("embed=False but given text.")
            if not self.embedding_service:
                raise RuntimeError("BaseEmbeddingService required but missing.")
            vec = self.embedding_service.embed(new_text_or_vector)
            new_text = new_text_or_vector
        else:
            # Raw vector update; preserve existing text
            if embed:
                raise ValueError("embed=True but raw vector supplied.")
            vec = new_text_or_vector
            new_text = existing.text

        # Normalize if needed
        vec = normalize_vector(vec) if self._normalize else vec

        # Merge/update metadata: preserve existing, apply new fields
        existing_meta = getattr(existing, "metadata", None) or {}
        new_meta = dict(existing_meta)
        new_meta.update(metadata)

        # Rebuild the record with updated vector/text/metadata
        updated = VectorRecord(
            id=id,
            vector=vec,
            text=new_text,
            metadata=new_meta,
        )

        self._vectors[id] = vec
        self._record[id] = updated

    # ---------- Misc ----------

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
            path: Folder or file path. If a folder (or not ending with .pkl),
                  'in_memory_store.pkl' is used within that folder.
        """
        pickle_path = Path(path or ".")
        if pickle_path.is_dir() or not str(pickle_path).endswith(".pkl"):
            pickle_path /= "in_memory_store.pkl"
        with open(pickle_path, "wb") as f:
            records_serialized = {
                rid: {
                    "id": rec.id,
                    "vector": rec.vector,
                    "text": rec.text,
                    "metadata": getattr(rec, "metadata", None),
                }
                for rid, rec in self._record.items()
            }

            pickle.dump(
                {
                    "metric": getattr(self.metric, "value", self.metric),
                    "dim": self._dim,
                    "normalize": self._normalize,
                    "vectors": self._vectors,
                    "record": records_serialized,
                },
                f,
            )

    @classmethod
    def load(cls, path: Union[str, Path]) -> "InMemoryVectorStore":
        """
        Load a vector store from a pickle file.

        Args:
            path: Path to the pickle file.

        Returns:
            An InMemoryVectorStore instance reloaded from disk.
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
        raw_records = data["record"]
        recs = {}
        for rid, rec in raw_records.items():
            if isinstance(rec, dict):
                recs[rid] = VectorRecord(
                    id=rec.get("id", rid),
                    vector=rec.get("vector"),
                    text=rec.get("text"),
                    metadata=rec.get("metadata"),
                )
            else:
                # Fallback: already an object (older pickle)
                recs[rid] = rec

        store._record = recs
        return store
