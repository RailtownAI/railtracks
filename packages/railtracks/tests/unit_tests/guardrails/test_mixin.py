"""Unit tests for LLMGuardrailsMixin."""

from __future__ import annotations

import pytest

from railtracks.guardrails.core import (
    Guard,
    GuardrailBlockedError,
    GuardrailDecision,
    LLMGuardrailPhase,
)
from railtracks.guardrails.llm.mixin import LLMGuardrailsMixin
from railtracks.llm import AssistantMessage, MessageHistory, UserMessage
from railtracks.nodes.nodes import DebugDetails
from railtracks.llm.providers import ModelProvider
from railtracks.llm.response import MessageInfo, Response


class _StubLLM:
    model_name = "stub-model"
    model_provider = ModelProvider.OPENAI


class _StubLLMCallableAttrs:
    def model_name(self):
        return "called-name"

    def model_provider(self):
        return ModelProvider.ANTHROPIC


class _StubWithDetails:
    """Minimal node-like `details` so mixin can append guardrail traces (matches LLMBase ordering)."""

    def __init__(self):
        self._details = DebugDetails()
        self._details["guard_details"] = []

    @property
    def details(self):
        return self._details


class GuardedTerminalStub(_StubWithDetails, LLMGuardrailsMixin):
    """Class name contains 'terminal' for agent_kind tagging."""

    guardrails: Guard | None = None
    llm_model = _StubLLM()
    uuid = "uuid-terminal"

    @classmethod
    def name(cls) -> str:
        return "Terminal LLM"


class GuardedStructuredStub(_StubWithDetails, LLMGuardrailsMixin):
    """Class name contains 'structured' for agent_kind tagging."""

    guardrails: Guard | None = None
    llm_model = _StubLLM()
    uuid = "uuid-structured"

    @classmethod
    def name(cls) -> str:
        return "Structured LLM (X)"


class GuardedOtherStub(_StubWithDetails, LLMGuardrailsMixin):
    guardrails: Guard | None = None
    llm_model = _StubLLM()
    uuid = "uuid-other"

    @classmethod
    def name(cls) -> str:
        return "Other"


def test_pre_invoke_no_guard_config():
    node = GuardedTerminalStub()
    node.guardrails = None
    mh = MessageHistory([UserMessage("x")])
    assert node._pre_invoke(mh) is mh


def test_pre_invoke_empty_input_rails():
    node = GuardedTerminalStub()
    node.guardrails = Guard(input=[])
    mh = MessageHistory([UserMessage("x")])
    assert node._pre_invoke(mh) is mh


def test_pre_invoke_blocks():
    node = GuardedTerminalStub()
    node.guardrails = Guard(
        input=[lambda _e: GuardrailDecision.block(reason="nope", user_facing_message="u")],
    )
    mh = MessageHistory([UserMessage("x")])
    with pytest.raises(GuardrailBlockedError) as exc_info:
        node._pre_invoke(mh)
    err = exc_info.value
    assert err.reason == "nope"
    assert err.user_facing_message == "u"
    assert err.traces
    assert err.traces[-1].action == "block"
    assert node.details["guard_details"] == err.traces


def test_pre_invoke_transforms_messages():
    new_hist = MessageHistory([UserMessage("y")])

    node = GuardedTerminalStub()
    node.guardrails = Guard(
        input=[
            lambda _e: GuardrailDecision.transform_messages(
                messages=new_hist, reason="edit"
            ),
        ],
    )
    mh = MessageHistory([UserMessage("x")])
    out = node._pre_invoke(mh)
    assert out == new_hist
    assert len(node.details["guard_details"]) == 1
    assert node.details["guard_details"][0].action == "transform"


def test_post_invoke_skips_when_not_response():
    node = GuardedTerminalStub()
    node.guardrails = Guard(
        output=[lambda _e: GuardrailDecision.block(reason="should not run")],
    )
    assert node._post_invoke(MessageHistory([]), {"not": "response"}) == {"not": "response"}


def test_post_invoke_skips_when_no_output_rails():
    node = GuardedTerminalStub()
    node.guardrails = Guard(output=[])
    resp = Response(
        message=AssistantMessage("ok"),
        message_info=MessageInfo(model_name="m"),
    )
    out = node._post_invoke(MessageHistory([UserMessage("q")]), resp)
    assert out is resp


def test_post_invoke_output_block():
    node = GuardedTerminalStub()
    node.guardrails = Guard(
        output=[lambda _e: GuardrailDecision.block(reason="bad output")],
    )
    resp = Response(
        message=AssistantMessage("evil"),
        message_info=MessageInfo(input_tokens=1, model_name="m"),
    )
    with pytest.raises(GuardrailBlockedError) as exc_info:
        node._post_invoke(MessageHistory([UserMessage("q")]), resp)
    assert exc_info.value.traces[-1].phase == "llm_output"
    assert node.details["guard_details"] == exc_info.value.traces


def test_post_invoke_output_transform_preserves_message_info():
    new_msg = AssistantMessage("sanitized")

    node = GuardedTerminalStub()
    node.guardrails = Guard(
        output=[
            lambda _e: GuardrailDecision.transform_output(
                output_message=new_msg, reason="fix"
            ),
        ],
    )
    info = MessageInfo(input_tokens=3, output_tokens=5, model_name="m")
    resp = Response(message=AssistantMessage("raw"), message_info=info)
    out = node._post_invoke(MessageHistory([UserMessage("q")]), resp)
    assert isinstance(out, Response)
    assert out.message == new_msg
    assert out.message_info is info
    assert len(node.details["guard_details"]) == 1
    assert node.details["guard_details"][0].action == "transform"


def test_pre_then_post_appends_guard_details_in_order():
    node = GuardedTerminalStub()
    node.guardrails = Guard(
        input=[lambda _e: GuardrailDecision.allow(reason="ok in")],
        output=[lambda _e: GuardrailDecision.allow(reason="ok out")],
    )
    mh = MessageHistory([UserMessage("x")])
    node._pre_invoke(mh)
    resp = Response(
        message=AssistantMessage("hi"),
        message_info=MessageInfo(model_name="m"),
    )
    node._post_invoke(mh, resp)
    assert len(node.details["guard_details"]) == 2
    assert node.details["guard_details"][0].phase == "llm_input"
    assert node.details["guard_details"][1].phase == "llm_output"


def test_build_input_event_tags_and_metadata():
    node = GuardedStructuredStub()
    node.llm_model = _StubLLMCallableAttrs()
    ctx = MessageHistory([UserMessage("q")])
    ev = node._build_input_event(ctx)
    assert ev.messages == ctx
    assert ev.phase == LLMGuardrailPhase.INPUT
    assert ev.model_name == "called-name"
    # Enum coerced with str() uses the default Enum __str__, not the value string.
    assert ev.model_provider == str(ModelProvider.ANTHROPIC)
    assert ev.tags == {"agent_kind": "structured"}
    assert ev.node_uuid == "uuid-structured"


def test_build_output_event_has_output_message():
    node = GuardedTerminalStub()
    ctx = MessageHistory([UserMessage("q")])
    assistant = AssistantMessage("a")
    ev = node._build_output_event(ctx, assistant)
    assert ev.output_message == assistant
    assert ev.phase == LLMGuardrailPhase.OUTPUT
    assert ev.tags == {"agent_kind": "terminal"}


def test_guardrail_agent_kind_fallback():
    node = GuardedOtherStub()
    assert node._guardrail_agent_kind() == "llm"
