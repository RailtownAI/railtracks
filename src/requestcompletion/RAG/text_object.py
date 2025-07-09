# text_object.py
from typing import Any, List, Optional
import os
import hashlib
import logging

logger = logging.getLogger(__name__)


class ResourceInstance:
    """Base class for any resource object (text, image, video, etc.)."""

    def __init__(
        self,
        path: Optional[str] = None,
        name: Optional[str] = None,
        type: Optional[str] = None,
        description: Optional[str] = "",
        tags: Optional[List[str]] = None,
        comment: Optional[str] = "",
        hash: Optional[str] = None,
        duration: Optional[float] = None,
        object: Any = None,
    ):
        self.path = self.normalize_path(path) if path else None
        self.name = name or (self.get_name_from_path(self.path) if self.path else None)
        self.type = type or "unknown"
        self.description = description or ""
        self.tags = tags or []
        self.comment = comment or ""
        self.hash = hash or (self.get_resource_hash(self.path) if self.path else "")
        self.duration = duration or 0
        self.object = object

    @staticmethod
    def normalize_path(path: str) -> str:
        return path.replace("\\", "/")

    @staticmethod
    def get_name_from_path(path: str) -> str:
        name = os.path.basename(path)
        return os.path.splitext(name)[0]

    @staticmethod
    def get_resource_hash(file_path: str, _hash_type="sha256") -> str:
        hash_obj = hashlib.new(_hash_type)
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                hash_obj.update(chunk)
        return hash_obj.hexdigest()

    def get_metadata(self) -> dict:
        """Serializable metadata dictionary."""
        return {
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "path": self.path,
            "tags": self.tags,
            "comment": self.comment,
            "hash": self.hash,
            "duration": self.duration,
        }

    def __str__(self):
        return f"<ResourceInstance name={self.name}, type={self.type}>"


class TextObject(ResourceInstance):
    """Text-specific metadata and embedding storage."""

    def __init__(self, raw_content: str, path: Optional[str] = None, **kwargs):
        super().__init__(path=path, type="text", **kwargs)
        self.raw_content: str = raw_content
        self.chunked_content: List[str] = []
        self.embeddings: List[List[float]] = []

    def set_chunked(self, chunks: List[str]):
        self.chunked_content = chunks

    def set_embeddings(self, vectors: List[List[float]]):
        self.embeddings = vectors

    def get_metadata(self) -> dict:
        meta = super().get_metadata()
        meta.update(
            {
                "raw_content": self.raw_content,
                "num_chunks": len(self.chunked_content),
                "embeddings": f"{len(self.embeddings)} vectors",
            }
        )
        return meta
