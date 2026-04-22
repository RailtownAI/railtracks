from __future__ import annotations

import re

from railtracks.guardrails.core.decision import GuardrailDecision
from railtracks.guardrails.core.event import LLMGuardrailEvent
from railtracks.guardrails.core.interfaces import OutputGuard


class BlockTextOutputGuard(OutputGuard):
    """Blocks LLM output when the assistant message matches a regex pattern."""

    def __init__(
        self,
        pattern: str,
        *,
        name: str | None = None,
        user_facing_message: str | None = None,
    ) -> None:
        """Initialize the output block-text guard.

        Args:
            pattern: Regex pattern; if it matches the output message content
                the guard returns ``BLOCK``.
            name: Optional rail name for traces (see :class:`OutputGuard`).
            user_facing_message: Optional message surfaced to UIs and
                visualizers when the guard blocks.

        Raises:
            re.error: If *pattern* is not a valid regular expression.
        """
        super().__init__(name=name)
        self._pattern = re.compile(pattern)
        self._user_facing_message = user_facing_message

    def __call__(self, event: LLMGuardrailEvent) -> GuardrailDecision:
        """Block if the output message matches the pattern.

        Returns:
            ``BLOCK`` when the pattern is found, ``ALLOW`` otherwise.
        """
        msg = event.output_message
        if msg is None or not isinstance(msg.content, str):
            return GuardrailDecision.allow(reason="No string output to scan.")

        if self._pattern.search(msg.content):
            return GuardrailDecision.block(
                reason=("Output blocked: prohibited content detected."),
                user_facing_message=self._user_facing_message,
            )
        return GuardrailDecision.allow(reason="No blocked patterns detected in output.")
