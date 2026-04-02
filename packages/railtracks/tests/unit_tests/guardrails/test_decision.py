"""Tests for GuardrailDecision factories."""

from __future__ import annotations

from railtracks.guardrails.core import GuardrailAction, GuardrailDecision
from railtracks.llm import AssistantMessage, MessageHistory, UserMessage


def test_allow_factory():
    d = GuardrailDecision.allow(reason="ok", meta={"k": 1})
    assert d.action == GuardrailAction.ALLOW
    assert d.reason == "ok"
    assert d.meta == {"k": 1}
    assert d.messages is None
    assert d.output_message is None


def test_block_factory():
    d = GuardrailDecision.block(
        reason="bad",
        user_facing_message="no",
        meta={"m": 2},
    )
    assert d.action == GuardrailAction.BLOCK
    assert d.user_facing_message == "no"
    assert d.meta == {"m": 2}


def test_transform_messages_factory():
    new_hist = MessageHistory([UserMessage("x")])
    d = GuardrailDecision.transform_messages(
        messages=new_hist, reason="trim", meta=None
    )
    assert d.action == GuardrailAction.TRANSFORM
    assert d.messages == new_hist


def test_transform_output_factory():
    msg = AssistantMessage(content="out")
    d = GuardrailDecision.transform_output(
        output_message=msg, reason="sanitize", meta={"a": True}
    )
    assert d.action == GuardrailAction.TRANSFORM
    assert d.output_message == msg
