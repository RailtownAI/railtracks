import pytest
from pydantic import BaseModel
from railtracks.built_nodes.concrete.response import LLMResponse, StructuredResponse, StringResponse

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
    assert resp.content == content
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
    assert repr(resp) == "LLMResponse(abc)"
