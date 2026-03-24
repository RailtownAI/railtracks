"""Round-trip tests for LLMGuardrailEvent (de)serialization."""

from __future__ import annotations

import pytest

from railtracks.guardrails.core import LLMGuardrailEvent, LLMGuardrailPhase
from railtracks.llm import (
    AssistantMessage,
    MessageHistory,
    SystemMessage,
    ToolCall,
    ToolMessage,
    ToolResponse,
    UserMessage,
)


def test_event_round_trip_string_messages():
    hist = MessageHistory(
        [
            SystemMessage("sys", inject_prompt=False),
            UserMessage("hello"),
            AssistantMessage("hi there"),
        ]
    )
    event = LLMGuardrailEvent(phase=LLMGuardrailPhase.INPUT, messages=hist)
    dumped = event.model_dump(mode="json")
    restored = LLMGuardrailEvent.model_validate(dumped)
    assert restored.phase == LLMGuardrailPhase.INPUT
    assert len(restored.messages) == 3
    assert restored.messages[0].content == "sys"
    assert restored.messages[1].content == "hello"
    assert restored.messages[2].content == "hi there"


def test_event_round_trip_assistant_with_tool_calls():
    calls = [
        ToolCall(identifier="1", name="fn", arguments={"x": 1}),
    ]
    hist = MessageHistory([AssistantMessage(content=calls)])
    event = LLMGuardrailEvent(phase=LLMGuardrailPhase.INPUT, messages=hist)
    restored = LLMGuardrailEvent.model_validate(event.model_dump(mode="json"))
    assert len(restored.messages) == 1
    content = restored.messages[0].content
    assert isinstance(content, list)
    assert len(content) == 1
    assert content[0].name == "fn"


def test_event_round_trip_tool_message():
    tr = ToolResponse(identifier="1", name="fn", result="ok")
    hist = MessageHistory([ToolMessage(content=tr)])
    event = LLMGuardrailEvent(phase=LLMGuardrailPhase.INPUT, messages=hist)
    restored = LLMGuardrailEvent.model_validate(event.model_dump(mode="json"))
    assert restored.messages[0].role.value == "tool"
    assert restored.messages[0].content.result == "ok"


def test_event_round_trip_output_message():
    hist = MessageHistory([UserMessage("q")])
    out = AssistantMessage("answer")
    event = LLMGuardrailEvent(
        phase=LLMGuardrailPhase.OUTPUT,
        messages=hist,
        output_message=out,
    )
    restored = LLMGuardrailEvent.model_validate(event.model_dump(mode="json"))
    assert restored.output_message is not None
    assert restored.output_message.content == "answer"


def test_event_rejects_invalid_messages_type():
    with pytest.raises(ValueError, match="messages"):
        LLMGuardrailEvent(phase=LLMGuardrailPhase.INPUT, messages="bad")  # type: ignore[arg-type]
