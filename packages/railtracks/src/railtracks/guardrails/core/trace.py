from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class GuardrailTrace(BaseModel):
    rail_name: str
    phase: str
    action: str
    reason: str
    meta: dict[str, Any] | None = None
