from __future__ import annotations

from copy import deepcopy

from railtracks.guardrails.core.decision import GuardrailDecision
from railtracks.guardrails.core.event import LLMGuardrailEvent
from railtracks.guardrails.core.interfaces import OutputGuard

from .._pii.config import PIIRedactConfig
from .._pii.engine import PIIEngine, build_redaction_meta


class PIIRedactOutputGuard(OutputGuard):
    """
    Output guardrail that redacts PII from the assistant's response after
    LLM generation.
    """

    def __init__(
        self,
        config: PIIRedactConfig | None = None,
        *,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name)
        self._config = config or PIIRedactConfig()
        self._engine = PIIEngine(self._config)

    def __call__(self, event: LLMGuardrailEvent) -> GuardrailDecision:
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
