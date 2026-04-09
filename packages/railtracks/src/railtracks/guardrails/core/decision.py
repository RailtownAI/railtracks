from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict

from railtracks.llm import Message, MessageHistory


class GuardrailAction(str, Enum):
    """What the runner should do after a guardrail returns.

    Members:
        ALLOW: Keep the current input or output unchanged.
        TRANSFORM: Replace input messages or the output message from the decision.
        BLOCK: Stop and treat the interaction as blocked.
    """

    ALLOW = "allow"
    TRANSFORM = "transform"
    BLOCK = "block"


class GuardrailDecision(BaseModel):
    """Result of one guardrail invocation.

    Which fields are set depends on :attr:`action`:

    * ``ALLOW``: only :attr:`reason` and optional :attr:`meta` are typically used.
    * ``TRANSFORM``: for input phase, :attr:`messages` holds the new history; for
      output phase, :attr:`output_message` holds the new assistant message.
    * ``BLOCK``: :attr:`user_facing_message` and :attr:`meta` may carry details for
      callers or UIs.
    """

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
        """Build an ``ALLOW`` decision with no content changes.

        Args:
            reason: Explanation for traces and debugging.
            meta: Optional extra fields for observability.

        Returns:
            A decision with :attr:`action` ``ALLOW``.
        """
        return cls(action=GuardrailAction.ALLOW, reason=reason, meta=meta)

    @classmethod
    def block(
        cls,
        reason: str,
        user_facing_message: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> "GuardrailDecision":
        """Build a ``BLOCK`` decision.

        Args:
            reason: Explanation for logs, traces, and raised errors.
            user_facing_message: Optional message safe to show to end users.
            meta: Optional extra fields (e.g. exception details).

        Returns:
            A decision with :attr:`action` ``BLOCK``.
        """
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
        """Build a ``TRANSFORM`` decision for LLM input (message history).

        Args:
            messages: Replacement conversation history for the model call.
            reason: Explanation for traces and debugging.
            meta: Optional extra fields (e.g. redaction counts).

        Returns:
            A decision with :attr:`action` ``TRANSFORM`` and :attr:`messages` set.
        """
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
        """Build a ``TRANSFORM`` decision for LLM output (assistant message).

        Args:
            output_message: Replacement assistant message to return.
            reason: Explanation for traces and debugging.
            meta: Optional extra fields (e.g. redaction counts).

        Returns:
            A decision with :attr:`action` ``TRANSFORM`` and :attr:`output_message`
            set.
        """
        return cls(
            action=GuardrailAction.TRANSFORM,
            reason=reason,
            output_message=output_message,
            meta=meta,
        )
