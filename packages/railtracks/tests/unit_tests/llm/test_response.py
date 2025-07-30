from railtracks.llm.response import Response
from railtracks.llm import AssistantMessage, UserMessage
import pytest


def test_response_with_streamer():
    def streamer():
        yield "chunk1"
        yield "chunk2"

    response = Response(streamer=streamer())
    assert response.streamer is not None
    assert list(response.streamer) == ["chunk1", "chunk2"]


def test_response_with_message_and_streamer():
    def streamer():
        yield "chunk1"
        yield "chunk2"

    message = AssistantMessage("Hello, I am an assistant.")
    response = Response(message=message, streamer=streamer())

    assert response.message == message
    assert response.message.content == "Hello, I am an assistant."
    assert response.message.role.value == "assistant"
    assert response.streamer is not None
    assert list(response.streamer) == ["chunk1", "chunk2"]


def test_response_without_message_or_streamer():
    response = Response()
    assert response.message is None
    assert response.streamer is None
    assert str(response) == "Response(<no-data>)"
    assert repr(response).startswith("Response(message=None, streamer=None")


def test_response_invalid_streamer_type():
    with pytest.raises(TypeError):
        Response(streamer="Invalid streamer")  # Streamer should be a generator


def test_message_str_and_repr():
    message = UserMessage("This is a user message.")
    assert str(message) == "user: This is a user message."
    assert repr(message) == "user: This is a user message."


def test_response_invalid_message_types():
    with pytest.raises(TypeError):
        Response(123)
