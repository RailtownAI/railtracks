from pydantic import BaseModel
from railtracks.built_nodes.llm.response import (
    LLMResponse,
    StringResponse,
    StructuredResponse,
)
from railtracks.llm import MessageHistory, ToolCall, UserMessage
from railtracks.llm.message import AssistantMessage, ToolMessage


class DummyContent:
    def __repr__(self):
        return "DummyContent()"


class DummyMessageHistory:
    def __repr__(self):
        return "DummyMessageHistory()"


class DummyModel(BaseModel):
    x: int


def test_llmresponse_repr():
    content = DummyContent()
    history = DummyMessageHistory()
    resp = LLMResponse(content, history)
    assert resp.content is content
    assert resp.message_history is history
    assert repr(resp) == "LLMResponse(DummyContent())"


def test_structured_response():
    model = DummyModel(x=42)
    history = DummyMessageHistory()
    resp = StructuredResponse(model, history)
    assert resp.content == model
    assert resp.message_history is history
    assert resp.structured == model


def test_string_response():
    content = "hello world"
    history = DummyMessageHistory()
    resp = StringResponse(content, history)
    assert resp.content == [content]
    assert resp.message_history is history
    assert resp.text == content


def test_structured_response_repr():
    model = DummyModel(x=99)
    history = DummyMessageHistory()
    resp = StructuredResponse(model, history)
    assert repr(resp) == f"LLMResponse({model})"


def test_string_response_repr():
    content = "abc"
    history = DummyMessageHistory()
    resp = StringResponse(content, history)
    assert repr(resp) == "LLMResponse(['abc'])"


def test_tool_invocations_empty_when_no_tool_calls():
    history = MessageHistory([UserMessage("hi"), AssistantMessage("hello")])
    resp = LLMResponse(content="hello", message_history=history)
    assert resp.tool_invocations == []


def test_tool_invocations_pairs_single_tool_call_with_its_response():
    tool_call = ToolCall(name="secret_phrase", identifier="id1", arguments={})
    tool_message = ToolMessage(
        "Constantinople", tool_call_id="id1", name="secret_phrase"
    )
    history = MessageHistory(
        [
            UserMessage("what's the secret phrase?"),
            AssistantMessage(content=[tool_call]),
            tool_message,
        ]
    )
    resp = LLMResponse(content="Constantinople", message_history=history)

    invocations = resp.tool_invocations

    assert len(invocations) == 1
    call, response = invocations[0]
    assert call == tool_call
    assert response is tool_message
    assert response.text == "Constantinople"


def test_tool_invocations_pairs_multiple_tool_calls_in_order():
    call_a = ToolCall(name="a", identifier="id_a", arguments={})
    call_b = ToolCall(name="b", identifier="id_b", arguments={})
    response_a = ToolMessage("ra", tool_call_id="id_a", name="a")
    response_b = ToolMessage("rb", tool_call_id="id_b", name="b")
    history = MessageHistory(
        [
            UserMessage("go"),
            AssistantMessage(content=["Running both.", call_a, call_b]),
            response_b,
            response_a,
        ]
    )
    resp = LLMResponse(content="done", message_history=history)

    invocations = resp.tool_invocations

    assert invocations == [(call_a, response_a), (call_b, response_b)]
