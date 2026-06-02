"""Input length guardrail — blocks LLM requests that exceed a character limit."""

from __future__ import annotations

from railtracks.guardrails.core.decision import GuardrailDecision
from railtracks.guardrails.core.event import LLMGuardrailEvent
from railtracks.guardrails.core.interfaces import InputGuard


class InputLengthGuard(InputGuard):
    """Blocks LLM input (the full message history) that exceeds ``max_chars`` characters.

    Character counting is used as the simplest, dependency-free unit.  A future
    implementation may add word- or token-based counting via an optional parameter.

    Example::

        guard = InputLengthGuard(max_chars=4000)

    Args:
        max_chars: Maximum number of characters allowed across all messages in the
            input history.  Defaults to ``4096``.
        name: Optional display name for the guardrail instance.
    """

    def __init__(self, max_chars: int = 4096, name: str | None = None) -> None:
        super().__init__(name=name)
        if max_chars <= 0:
            raise ValueError(f"max_chars must be a positive integer, got {max_chars!r}")
        self.max_chars = max_chars

    def __call__(self, event: LLMGuardrailEvent) -> GuardrailDecision:
        total_chars = sum(len(m.content or "") for m in event.messages)
        if total_chars > self.max_chars:
            return GuardrailDecision.block(
                reason=(
                    f"Input length {total_chars} characters exceeds the maximum of "
                    f"{self.max_chars} characters."
                ),
                user_facing_message=(
                    "Your message is too long. Please shorten your input and try again."
                ),
                meta={"total_chars": total_chars, "max_chars": self.max_chars},
            )
        return GuardrailDecision.allow(
            reason=f"Input length {total_chars} chars is within the {self.max_chars}-char limit.",
            meta={"total_chars": total_chars, "max_chars": self.max_chars},
        )
