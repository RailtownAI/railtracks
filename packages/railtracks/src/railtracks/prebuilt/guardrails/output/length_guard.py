"""Output length guardrail — blocks LLM responses that exceed a character limit."""

from __future__ import annotations

from railtracks.guardrails.core.decision import GuardrailDecision
from railtracks.guardrails.core.event import LLMGuardrailEvent
from railtracks.guardrails.llm.concrete import OutputGuard
from railtracks.prebuilt.guardrails._length import message_char_count


class OutputLengthGuard(OutputGuard):
    """Blocks LLM output that exceeds ``max_chars`` characters.

    Inspects ``event.output_message`` (the assistant reply produced this turn).

    Content that is not a plain string (tool-call turns, structured pydantic
    models) is counted via
    :func:`~railtracks.prebuilt.guardrails._length.message_char_count`.

    Example::

        guard = OutputLengthGuard(max_chars=2000)

    Args:
        max_chars: Maximum number of characters allowed in the assistant reply.
            Defaults to ``2048``.
        name: Optional display name for the guardrail instance.
        fail_open: Whether to allow the response to continue when this guard raises
            an unexpected exception.
    """

    def __init__(
        self, max_chars: int = 2048, name: str | None = None, fail_open: bool = False
    ) -> None:
        super().__init__(name=name, fail_open=fail_open)
        if max_chars <= 0:
            raise ValueError(f"max_chars must be a positive integer, got {max_chars!r}")
        self.max_chars = max_chars

    def __call__(self, event: LLMGuardrailEvent) -> GuardrailDecision:
        if event.output_message is None:
            return GuardrailDecision.allow(reason="No output message to evaluate.")

        total_chars = message_char_count(event.output_message.content)
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
