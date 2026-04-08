from __future__ import annotations

from copy import deepcopy

from railtracks.guardrails.core.decision import GuardrailDecision
from railtracks.guardrails.core.event import LLMGuardrailEvent
from railtracks.guardrails.core.interfaces import InputGuard
from railtracks.llm.history import MessageHistory
from railtracks.llm.message import Message, Role

from .._pii.config import PIIRedactConfig
from .._pii.engine import PIIEngine, RedactionRecord, build_redaction_meta

_SCANNABLE_ROLES = frozenset({Role.user, Role.system})


class PIIRedactInputGuard(InputGuard):
    """
    Input guardrail that redacts PII from user and system messages before
    they reach the LLM.
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
        all_records: list[RedactionRecord] = []
        new_messages: list[Message] = []
        messages_affected = 0

        for msg in event.messages:
            if msg.role not in _SCANNABLE_ROLES or not isinstance(msg.content, str):
                new_messages.append(msg)
                continue

            redacted_text, records = self._engine.redact(msg.content)
            if records:
                all_records.extend(records)
                messages_affected += 1
                clone = deepcopy(msg)
                clone._content = redacted_text
                new_messages.append(clone)
            else:
                new_messages.append(msg)

        if not all_records:
            return GuardrailDecision.allow(reason="No PII detected in input.")

        return GuardrailDecision.transform_messages(
            messages=MessageHistory(new_messages),
            reason=f"Redacted {len(all_records)} PII span(s) from input messages.",
            meta=build_redaction_meta(all_records, messages_affected=messages_affected),
        )
