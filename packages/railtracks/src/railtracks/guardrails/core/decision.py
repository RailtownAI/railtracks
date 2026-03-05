from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict

from railtracks.llm import Message, MessageHistory


class GuardrailAction(str, Enum):
    ALLOW = "allow"
    TRANSFORM = "transform"
    BLOCK = "block"


class GuardrailDecision(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    action: GuardrailAction
    reason: str
    messages: MessageHistory | None = None
    output_message: Message | None = None
    user_facing_message: str | None = None
    meta: dict[str, Any] | None = None

    @classmethod
    def allow(
        cls, reason: str = "Allowed by guardrail.", meta: dict[str, Any] | None = None
    ) -> "GuardrailDecision":
        return cls(action=GuardrailAction.ALLOW, reason=reason, meta=meta)

    @classmethod
    def block(
        cls,
        reason: str,
        user_facing_message: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> "GuardrailDecision":
        return cls(
            action=GuardrailAction.BLOCK,
            reason=reason,
            user_facing_message=user_facing_message,
            meta=meta,
        )

    @classmethod
    def transform_messages(
        cls,
        messages: MessageHistory,
        reason: str,
        meta: dict[str, Any] | None = None,
    ) -> "GuardrailDecision":
        return cls(
            action=GuardrailAction.TRANSFORM,
            reason=reason,
            messages=messages,
            meta=meta,
        )

    @classmethod
    def transform_output(
        cls,
        output_message: Message,
        reason: str,
        meta: dict[str, Any] | None = None,
    ) -> "GuardrailDecision":
        return cls(
            action=GuardrailAction.TRANSFORM,
            reason=reason,
            output_message=output_message,
            meta=meta,
        )
