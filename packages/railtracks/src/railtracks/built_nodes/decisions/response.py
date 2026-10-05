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
        cost: Cost in USD, or None when the model is not in the pricing table.
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
