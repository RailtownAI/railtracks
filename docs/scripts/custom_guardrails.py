"""Runnable examples for authoring custom guardrails.

Two ways to build a guard:
  1. the decorator API (``@rt.input_guard`` / ``@rt.output_guard``) — quickest,
  2. subclassing ``InputGuard`` / ``OutputGuard`` — for reusable, configurable rails.

Snippet regions (--8<-- [start:name]) are pulled into the guardrails docs by
MkDocs. Type-checked in CI via scripts/docs_validation.sh.
"""

from __future__ import annotations

import railtracks as rt

# --8<-- [start: decorator_imports]
from railtracks.guardrails import GuardrailDecision, LLMGuardrailEvent

# --8<-- [end: decorator_imports]


# --8<-- [start: decorator_input]
@rt.input_guard
def block_passwords(event: LLMGuardrailEvent) -> GuardrailDecision:
    """Block any input that asks for a password."""
    for message in event.messages:
        if isinstance(message.content, str) and "password" in message.content.lower():
            return GuardrailDecision.block(
                reason="Requests for passwords are not allowed.",
                user_facing_message="Ask for something else instead.",
            )
    return GuardrailDecision.allow()
# --8<-- [end: decorator_input]


# --8<-- [start: decorator_output]
@rt.output_guard(name="no_sign_off", fail_open=True)
def strip_sign_off(event: LLMGuardrailEvent) -> GuardrailDecision:
    """Rewrite the final reply to drop a trailing sign-off line."""
    content = event.output_message.content if event.output_message else None
    if not isinstance(content, str) or "\nBest," not in content:
        return GuardrailDecision.allow()
    trimmed = content.split("\nBest,")[0].rstrip()
    return GuardrailDecision.transform_output(
        rt.llm.AssistantMessage(trimmed),
        reason="Removed sign-off.",
    )
# --8<-- [end: decorator_output]


# --8<-- [start: decorator_attach]
Agent = rt.agent_node(
    name="custom-guard-demo",
    llm=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You are a concise assistant.",
    model_middleware=[block_passwords, strip_sign_off],
)
# --8<-- [end: decorator_attach]


# --8<-- [start: subclass_imports]
from railtracks.guardrails import InputGuard

# --8<-- [end: subclass_imports]


# --8<-- [start: subclass]
class BlockKeywordGuard(InputGuard):
    """A reusable input guard that blocks a configurable keyword."""

    def __init__(self, keyword: str, *, name: str | None = None) -> None:
        super().__init__(name=name)
        self._keyword = keyword.lower()

    def __call__(self, event: LLMGuardrailEvent) -> GuardrailDecision:
        for message in event.messages:
            if isinstance(message.content, str) and self._keyword in message.content.lower():
                return GuardrailDecision.block(
                    reason=f"Blocked keyword: {self._keyword}.",
                )
        return GuardrailDecision.allow()


guard = BlockKeywordGuard("password", name="BlockPassword")
# --8<-- [end: subclass]
