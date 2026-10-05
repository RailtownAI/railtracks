from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic, TypeVar

if TYPE_CHECKING:
    from ._base import DecisionSchema

_TSchema = TypeVar("_TSchema", bound="DecisionSchema")


@dataclass(frozen=True)
class DecisionResponse(Generic[_TSchema]):
    """The result of one decision request.

    Attributes:
        structured: The schema instance holding one answer per question.
        model_name: The model that answered, as reported by the provider (falls back
            to the requested name).
        provider: The provider that served the request, when reported.
        input_tokens: Input tokens, when reported.
        output_tokens: Output tokens, when reported.
        latency: Seconds the call took, including retries.
        cost: Cost in USD: what the host reported billing (OpenRouter's
            ``usage.cost``), else the LiteLLM pricing table's price, else None.
        raw: The parsed JSON body, for debugging.
    """

    structured: _TSchema
    model_name: str
    provider: str | None
    input_tokens: int | None
    output_tokens: int | None
    latency: float
    cost: float | None
    raw: dict[str, Any]

    def __str__(self) -> str:
        """One ``name: answer`` segment per question, in definition order.

        This is what an agent reads when the decision node is one of its tools.
        """
        return " | ".join(
            f"{name}: {answer}" for name, answer in self.structured._answers.items()
        )

    def encode(self) -> dict[str, Any]:
        """Plain JSON for the session record; ``raw`` is left out as it repeats the answers."""
        return {
            "structured": self.structured.encode(),
            "model_name": self.model_name,
            "provider": self.provider,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "latency": self.latency,
            "cost": self.cost,
        }
