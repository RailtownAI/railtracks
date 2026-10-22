"""PDF loading options shared by the PDF, OCR and cloud loaders.

Kept free of `pypdf` so loaders that only sometimes meet a PDF can validate
their options without the `pdf` extra installed.
"""

from __future__ import annotations

from collections.abc import Collection
from typing import Literal, get_args

BreakdownStrategy = Literal["page", "paragraph", "document"]

_BREAKDOWN_STRATEGIES: tuple[str, ...] = get_args(BreakdownStrategy)


def validate_breakdown_strategy(
    breakdown_strategy: str,
    *,
    name: str = "breakdown_strategy",
    allowed: Collection[str] = _BREAKDOWN_STRATEGIES,
) -> None:
    """Raise a `ValueError` unless `breakdown_strategy` is one of `allowed`.

    Args:
        breakdown_strategy: The value to check.
        name: The parameter name shown in the error message.
        allowed: The accepted strategies. Defaults to every
            `BreakdownStrategy`; loaders that support fewer pass their own.

    Raises:
        ValueError: If `breakdown_strategy` is not in `allowed`.
    """
    if breakdown_strategy not in allowed:
        choices = ", ".join(repr(strategy) for strategy in allowed)
        raise ValueError(f"{name} must be one of {choices}, got {breakdown_strategy!r}")
