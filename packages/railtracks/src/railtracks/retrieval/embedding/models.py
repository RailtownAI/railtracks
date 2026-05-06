from __future__ import annotations

from dataclasses import dataclass, field

from ..models import Chunk, EmbeddedChunk


@dataclass
class EmbeddingMetrics:
    """Usage and performance metrics for a single embedding call.

    Attributes:
        input_tokens: Number of tokens in the input, if reported by the provider.
        total_cost: Estimated cost in USD, if reported by the provider.
        latency: Wall-clock time in seconds for the embedding call.
        vector_count: Number of vectors returned.
        model: Provider-reported model identifier.
        dimension: Vector dimensionality.
    """

    input_tokens: int | None = None
    total_cost: float | None = None
    latency: float = 0.0
    vector_count: int = 0
    model: str | None = None
    dimension: int | None = None

    def __add__(self, other: EmbeddingMetrics) -> EmbeddingMetrics:
        if self.model and other.model:
            if self.model.split("/")[-1] != other.model.split("/")[-1]:
                raise ValueError(
                    f"Cannot add EmbeddingMetrics with different models: {self.model!r} vs {other.model!r}"
                )
        if self.dimension and other.dimension and self.dimension != other.dimension:
            raise ValueError(
                f"Cannot add EmbeddingMetrics with different dimensions: {self.dimension} vs {other.dimension}"
            )
        tokens = [x for x in (self.input_tokens, other.input_tokens) if x is not None]
        costs = [x for x in (self.total_cost, other.total_cost) if x is not None]
        return EmbeddingMetrics(
            input_tokens=sum(tokens) if tokens else None,
            total_cost=sum(costs) if costs else None,
            latency=self.latency + other.latency,
            vector_count=self.vector_count + other.vector_count,
            model=self.model if self.model is not None else other.model,
            dimension=self.dimension if self.dimension is not None else other.dimension,
        )


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
