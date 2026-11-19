from __future__ import annotations

from railtracks.guardrails.core.decision import GuardrailDecision
from railtracks.guardrails.core.event import LLMGuardrailEvent
from railtracks.guardrails.llm.concrete import InputGuard
from railtracks.llm.history import MessageHistory
from railtracks.llm.message import Message, Role

from .._pii.config import PIIRedactConfig
from .._pii.engine import PIIEngine, RedactionRecord, build_redaction_meta

_SCANNABLE_ROLES = frozenset({Role.user, Role.system})


class PIIRedactInputGuard(InputGuard):
    """Redacts PII from the text of user and system messages before they reach the LLM."""

    def __init__(
        self,
        config: PIIRedactConfig | None = None,
        *,
        name: str | None = None,
        fail_open: bool = False,
    ) -> None:
        """Initialize the input PII redactor.

        Args:
            config: Redaction settings; defaults to all built-in entity kinds and no
                custom patterns (see :class:`~railtracks.prebuilt.guardrails.PIIRedactConfig`).
            name: Optional rail name for traces (see :class:`InputGuard`).
            fail_open: Whether to allow the request to continue when this guard raises an unexpected exception.
        """
        super().__init__(name=name, fail_open=fail_open)
        self._config = config or PIIRedactConfig()
        self._engine = PIIEngine(self._config)

    def __call__(self, event: LLMGuardrailEvent) -> GuardrailDecision:
        """Scan the text of user/system messages and redact matches.

        Returns:
            ``ALLOW`` when no PII is found, or ``TRANSFORM`` with rewritten messages on
            :attr:`~railtracks.guardrails.core.decision.GuardrailDecision.messages`
            and redaction metadata in ``meta``.
        """
        all_records: list[RedactionRecord] = []
        new_messages: list[Message] = []
        messages_affected = 0

        for msg in event.messages:
            if msg.role not in _SCANNABLE_ROLES:
                new_messages.append(msg)
                continue

            redacted, records = self._engine.redact_message(msg)
            if records:
                all_records.extend(records)
                messages_affected += 1
            new_messages.append(redacted)

        if not all_records:
            return GuardrailDecision.allow(reason="No PII detected in input.")

        return GuardrailDecision.transform_messages(
            messages=MessageHistory(new_messages),
            reason=f"Redacted {len(all_records)} PII span(s) from input messages.",
            meta=build_redaction_meta(all_records, messages_affected=messages_affected),
        )
