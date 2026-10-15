"""What a decision is about: text, or a JSON object or array sent as JSON text."""

from __future__ import annotations

from typing import Any, Union

from typing_extensions import TypeAlias

DecisionInput: TypeAlias = Union[str, dict[str, Any], list[Any]]
"""What a decision is about: text, or a JSON object or array (sent as JSON text)."""
