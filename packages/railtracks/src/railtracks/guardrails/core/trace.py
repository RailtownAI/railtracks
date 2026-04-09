from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class GuardrailTrace(BaseModel):
    """One guardrail step recorded during a run (for logging or debugging).

    Attributes:
        rail_name: The guard's :attr:`~railtracks.guardrails.core.interfaces.BaseGuardrail.name`
            or class name if unset.
        phase: ``LLMGuardrailPhase`` value string (e.g. ``llm_input``).
        action: ``allow``, ``transform``, ``block``, or ``error`` when the runner
            caught an exception, invalid return type, or unknown action.
        reason: Short explanation, or a fixed message for error traces.
        meta: Optional details (e.g. :attr:`GuardrailDecision.meta` or exception info).
    """

    rail_name: str
    phase: str
    action: str
    reason: str
    meta: dict[str, Any] | None = None
