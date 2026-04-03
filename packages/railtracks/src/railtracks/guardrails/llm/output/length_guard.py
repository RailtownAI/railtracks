"""Output length guardrail — blocks LLM responses that exceed a character limit."""

from __future__ import annotations

from railtracks.guardrails.core.decision import GuardrailDecision
from railtracks.guardrails.core.event import LLMGuardrailEvent
from railtracks.guardrails.core.interfaces import OutputGuard


class OutputLengthGuard(OutputGuard):
    """Blocks LLM output that exceeds ``max_chars`` characters.

    Inspects ``event.output_message`` (the assistant reply produced this turn).

    Example::

        guard = OutputLengthGuard(max_chars=2000)

    Args:
        max_chars: Maximum number of characters allowed in the assistant reply.
            Defaults to ``2048``.
        name: Optional display name for the guardrail instance.
    """

    def __init__(self, max_chars: int = 2048, name: str | None = None) -> None:
        super().__init__(name=name)
        if max_chars <= 0:
            raise ValueError(f"max_chars must be a positive integer, got {max_chars!r}")
        self.max_chars = max_chars

    def __call__(self, event: LLMGuardrailEvent) -> GuardrailDecision:
        if event.output_message is None:
            return GuardrailDecision.allow(reason="No output message to evaluate.")

        content = event.output_message.content or ""
        total_chars = len(content)
        if total_chars > self.max_chars:
            return GuardrailDecision.block(
                reason=(
                    f"Output length {total_chars} characters exceeds the maximum of "
                    f"{self.max_chars} characters."
                ),
                user_facing_message=(
                    "The response was too long and has been blocked. "
                    "Please try a more specific question."
                ),
                meta={"total_chars": total_chars, "max_chars": self.max_chars},
            )
        return GuardrailDecision.allow(
            reason=f"Output length {total_chars} chars is within the {self.max_chars}-char limit.",
            meta={"total_chars": total_chars, "max_chars": self.max_chars},
        )
