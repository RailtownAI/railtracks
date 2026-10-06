"""The vendor-neutral System One model client base."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from .schema import DecisionSchema

_TSchema = TypeVar("_TSchema", bound=DecisionSchema)


@dataclass(frozen=True)
class DecisionReply(Generic[_TSchema]):
    """What a vendor's transport returns for one successful request."""

    structured: _TSchema
    reported_model_name: str | None
    provider: str | None
    input_tokens: int | None
    output_tokens: int | None
    reported_cost: float | None
    raw: dict[str, Any]
