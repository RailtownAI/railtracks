"""Message content as an ordered list of text and attachments."""

from copy import deepcopy

import pytest
from pydantic import BaseModel
from railtracks.built_nodes.llm.llm_helpers import process_message
from railtracks.llm import (
    AssistantMessage,
    Attachment,
    SystemMessage,
    ToolCall,
    ToolCalls,
    ToolMessage,
    ToolResponse,
    UserMessage,
)
from railtracks.llm.history import MessageHistory
from railtracks.llm.message import (
    Message,
    Role,
    content_attachments,
    content_text,
    encode_content,
)
from railtracks.llm.response import Response
from railtracks.prebuilt.guardrails._length import message_char_count

_PNG = b"\x89PNG\r\n\x1a\n" + bytes(range(32))
_PDF = b"%PDF-1.7\n" + bytes(64)


@pytest.fixture
def image() -> Attachment:
    return Attachment.from_bytes(_PNG, filename="chart.png")


@pytest.fixture
def pdf() -> Attachment:
    return Attachment.from_bytes(_PDF, filename="report.pdf")


class _Answer(BaseModel):
    value: int


# ================================ UserMessage ================================


def test_text_is_a_single_part():
    message = UserMessage("Hello")
    assert message.content == ["Hello"]
    assert message.text == "Hello"
    assert message.attachments == []


def test_interleaved_parts_keep_their_order(image, pdf):
    parts = ["Before:", image, "After:", pdf, "Compare them."]
    message = UserMessage(parts)

    assert message.content == parts
    assert message.attachments == [image, pdf]
    assert message.text == "Before:\nAfter:\nCompare them."


def test_content_is_copied_from_the_caller_list(image):
    parts = ["Look:", image]
    message = UserMessage(parts)
    parts.append("mutated")
    assert message.content == ["Look:", image]


def test_tuple_and_single_attachment_are_accepted(image):
    assert UserMessage(("a", image)).content == ["a", image]
    assert UserMessage(image).content == [image]


def test_attachment_argument_goes_after_the_text(image):
    message = UserMessage("Describe this.", attachment=image)
    assert message.content == ["Describe this.", image]


def test_attachment_argument_goes_after_a_parts_list(image, pdf):
    message = UserMessage(["First:", image], attachment=pdf)
    assert message.content == ["First:", image, pdf]


def test_attachment_only_has_no_empty_text_part(image):
    message = UserMessage(attachment=image)
    assert message.content == [image]
    assert message.text == ""


@pytest.mark.parametrize(
    "content, error, match",
    [
        (None, ValueError, "needs text or at least one attachment"),
        ([], ValueError, "needs text or at least one attachment"),
        (["text", 3], TypeError, "must be str or Attachment, but got int"),
        (b"raw", TypeError, "must be a str, an Attachment or a list"),
        ([b"raw"], TypeError, "Attachment.from_bytes"),
        ({"text": "hi"}, TypeError, "must be a str, an Attachment or a list"),
    ],
)
def test_invalid_content_is_rejected(content, error, match):
    with pytest.raises(error, match=match):
        UserMessage(content)


def test_deprecated_attachment_view(image):
    with pytest.warns(DeprecationWarning, match="attachments"):
        assert UserMessage("hi", attachment=image).attachment == [image]
    with pytest.warns(DeprecationWarning):
        assert UserMessage("hi").attachment is None


def test_fill_prompt_fills_text_parts_only(image):
    message = UserMessage(["Hi {name}:", image, "from {place}"])
    message.fill_prompt({"name": "Ada", "place": "London"})
    assert message.content == ["Hi Ada:", image, "from London"]
    assert message.content[1] is image


def test_str_renders_each_part_on_its_own_line(image):
    assert str(UserMessage("Hello")) == "user: Hello"
    rendered = str(UserMessage(["Look:", image]))
    assert rendered == f"user: Look:\n{image!r}"


def test_deepcopy_copies_the_list_and_shares_attachments(image):
    message = UserMessage(["a", image])
    clone = deepcopy(message)
    assert clone.content == message.content
    assert clone.content is not message.content
    assert clone.content[1] is image


# =============================== Session JSON ================================


def test_encode_text_only_message_is_a_string():
    assert UserMessage("Hello").encode() == {"role": "user", "content": "Hello"}
    assert AssistantMessage("Hi").encode() == {"role": "assistant", "content": "Hi"}


def test_encode_with_attachments_keeps_the_session_json_shape(image, pdf):
    message = UserMessage(["Before:", image, "After:", pdf])
    assert message.encode() == {
        "role": "user",
        "content": [
            {"type": "text", "text": "Before:\nAfter:"},
            {"modality": "image", "type": "data_uri", "info": "..."},
            {"modality": "document", "type": "data_uri", "info": "..."},
        ],
    }


def test_encode_attachment_only_has_an_empty_text_part(image):
    assert UserMessage(attachment=image).encode()["content"][0] == {
        "type": "text",
        "text": "",
    }


def test_encode_content_leaves_other_content_alone():
    calls = ToolCalls([ToolCall(identifier="1", name="f", arguments={})])
    assert encode_content(calls) is calls
    answer = _Answer(value=1)
    assert encode_content(answer) is answer


# ============================== AssistantMessage =============================


def test_assistant_text_and_none_are_normalized():
    assert AssistantMessage("Hi").content == ["Hi"]
    assert AssistantMessage(None).content == []
    assert AssistantMessage(None).text == ""


def test_assistant_reply_with_media_is_not_a_tool_call(image):
    message = AssistantMessage(["Here is your logo:", image])
    assert message.content == ["Here is your logo:", image]
    assert message.tool_calls == []
    assert message.attachments == [image]


def test_assistant_list_of_tool_calls_becomes_tool_calls():
    call = ToolCall(identifier="1", name="f", arguments={"x": 1})
    message = AssistantMessage([call])
    assert isinstance(message.content, ToolCalls)
    assert message.tool_calls == [call]
    assert message.text == ""


def test_assistant_mixing_tool_calls_and_text_is_rejected():
    call = ToolCall(identifier="1", name="f", arguments={})
    with pytest.raises(TypeError, match="must be str or Attachment"):
        AssistantMessage([call, "text"])


def test_assistant_structured_output_is_kept():
    answer = _Answer(value=4)
    message = AssistantMessage(answer)
    assert message.content is answer
    assert message.text == ""
    assert message.attachments == []


# =============================== Views on content ============================


def test_text_view_for_every_message_kind():
    call = ToolCall(identifier="1", name="f", arguments={})
    assert SystemMessage("Be brief.").text == "Be brief."
    assert AssistantMessage(ToolCalls([call], text="Checking.")).text == "Checking."
    assert AssistantMessage(ToolCalls([call])).text == ""
    tool = ToolMessage(ToolResponse(identifier="1", name="f", result="42"))
    assert tool.text == "42"


def test_content_helpers_accept_plain_strings(image):
    assert content_text("plain") == "plain"
    assert content_attachments("plain") == []
    assert content_text(["a", image, "b"]) == "a\nb"


# ================================== Response =================================


def test_response_text_and_attachments(image):
    response = Response(AssistantMessage(["Here:", image]))
    assert response.text == "Here:"
    assert response.attachments == [image]


def test_response_text_for_tool_calls_is_the_spoken_text():
    call = ToolCall(identifier="1", name="f", arguments={})
    response = Response(AssistantMessage(ToolCalls([call], text="One moment.")))
    assert response.text == "One moment."


def test_response_text_raises_for_structured_output():
    response = Response(AssistantMessage(_Answer(value=1)))
    with pytest.raises(TypeError, match="structured output"):
        _ = response.text


# ========================= Custom models on the base Message =================


def test_base_message_with_a_tool_call_list_still_has_tool_calls():
    call = ToolCall(identifier="1", name="f", arguments={})
    message = Message(content=[call], role=Role.assistant)
    assert message.tool_calls == [call]
    assert Message(content=["text"], role=Role.assistant).tool_calls == []


def test_agent_accepts_a_plain_string_reply_from_a_base_message():
    reply = Response(Message(content="from a custom model", role=Role.assistant))
    assert process_message(reply, None, message_history=MessageHistory()) == "Content"
    assert AssistantMessage(reply.message.content).content == ["from a custom model"]


def test_encode_empty_reply_is_null():
    assert AssistantMessage(None).encode() == {"role": "assistant", "content": None}
    assert AssistantMessage("").encode() == {"role": "assistant", "content": ""}


def test_length_count_matches_text_and_counts_plain_tool_call_lists(image):
    parts = ["ab", image, "cd"]
    assert message_char_count(parts) == len(content_text(parts))
    call = ToolCall(identifier="1", name="f", arguments={"x": 1})
    assert message_char_count([call]) == message_char_count(ToolCalls([call]))
    assert message_char_count(ToolCalls([call], text="hi")) > message_char_count(
        ToolCalls([call])
    )
