from __future__ import annotations

from dataclasses import dataclass, field

from ..models import Chunk, EmbeddedChunk, EmbeddingMetrics


@dataclass
class TextEmbeddings:
    """Result of aembed(list[str]): raw vectors plus per-call metrics."""

    vectors: list[list[float]]
    metrics: EmbeddingMetrics = field(default_factory=EmbeddingMetrics)


@dataclass
class EmbeddingResult:
    """A successful batch embedding result.

    Attributes:
        chunks: Embedded chunks with their vectors attached.
        metrics: Usage and performance metrics for this batch.
    """

    chunks: list[EmbeddedChunk]
    metrics: EmbeddingMetrics = field(default_factory=EmbeddingMetrics)


@dataclass
class EmbeddingFailure:
    """A failed batch embedding attempt.

    Attributes:
        chunks: Source chunks that could not be embedded.
        errors: Exceptions raised during embedding.
    """

    chunks: list[Chunk]
    errors: list[Exception]


@dataclass
class MultimodalInput:
    """A single multimodal embedding input.

    Attributes:
        text: Text component of the input.
        image_url: URL or base64 data URI for the image component.
        metadata: Arbitrary key-value pairs for caller use.
    """

    text: str | None = None
    image_url: str | None = None  # URL or base64 data URI
    metadata: dict = field(default_factory=dict)
