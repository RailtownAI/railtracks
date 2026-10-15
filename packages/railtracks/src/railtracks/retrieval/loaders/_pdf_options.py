"""PDF loading options shared by `PyPDFLoader` and the cloud loaders.

Kept free of `pypdf` so loaders that only sometimes meet a PDF can validate
their options without the `pdf` extra installed.
"""

from __future__ import annotations

from typing import Literal, get_args

BreakdownStrategy = Literal["page", "paragraph", "document"]

_BREAKDOWN_STRATEGIES: tuple[str, ...] = get_args(BreakdownStrategy)


def validate_breakdown_strategy(
    breakdown_strategy: str, *, name: str = "breakdown_strategy"
) -> None:
    """Raise a `ValueError` unless `breakdown_strategy` is a known strategy.

    Args:
        breakdown_strategy: The value to check.
        name: The parameter name shown in the error message.

    Raises:
        ValueError: If `breakdown_strategy` is not `page`, `paragraph`, or
            `document`.
    """
    if breakdown_strategy not in _BREAKDOWN_STRATEGIES:
        raise ValueError(
            f"{name} must be 'page', 'paragraph', or 'document', "
            f"got {breakdown_strategy!r}"
        )
