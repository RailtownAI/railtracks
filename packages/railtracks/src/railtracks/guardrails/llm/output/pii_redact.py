from __future__ import annotations

from copy import deepcopy

from railtracks.guardrails.core.decision import GuardrailDecision
from railtracks.guardrails.core.event import LLMGuardrailEvent
from railtracks.guardrails.core.interfaces import OutputGuard

from .._pii.config import PIIRedactConfig
from .._pii.engine import PIIEngine, build_redaction_meta


class PIIRedactOutputGuard(OutputGuard):
    """Redacts PII from the assistant string response after LLM generation."""

    def __init__(
        self,
        config: PIIRedactConfig | None = None,
        *,
        name: str | None = None,
    ) -> None:
        """Initialize the output PII redactor.

        Args:
            config: Which built-in entities and custom patterns to apply; defaults to
                all built-in entity kinds.
            name: Optional rail name for traces (see :class:`OutputGuard`).
        """
        super().__init__(name=name)
        self._config = config or PIIRedactConfig()
        self._engine = PIIEngine(self._config)

    def __call__(self, event: LLMGuardrailEvent) -> GuardrailDecision:
        """Redact PII from string assistant content on ``event.output_message``.

        Returns:
            ``ALLOW`` when there is nothing to scan or no PII, or ``TRANSFORM`` with the
            rewritten message on
            :attr:`~railtracks.guardrails.core.decision.GuardrailDecision.output_message`
            and redaction metadata in ``meta``.
        """
        msg = event.output_message
        if msg is None or not isinstance(msg.content, str):
            return GuardrailDecision.allow(reason="No string output to scan.")

        redacted_text, records = self._engine.redact(msg.content)
        if not records:
            return GuardrailDecision.allow(reason="No PII detected in output.")

        clone = deepcopy(msg)
        clone._content = redacted_text
        return GuardrailDecision.transform_output(
            output_message=clone,
            reason=f"Redacted {len(records)} PII span(s) from output.",
            meta=build_redaction_meta(records),
        )
