"""Tests for the notices ahead of 1.9.0, where `.content` becomes a list of parts.

Every notice has two halves, and both are tested:

1. Reading `.content` from user code emits a `FutureWarning` naming the readers to use.
2. Those readers, and every read railtracks makes itself, are silent, so a user who
   migrates gets a clean run.
"""

from __future__ import annotations

import pytest
import railtracks as rt
from pydantic import BaseModel
from railtracks.built_nodes.llm.response import StringResponse, StructuredResponse
from railtracks.llm import (
    AssistantMessage,
    MessageHistory,
    SystemMessage,
    ToolCall,
    ToolMessage,
    ToolResponse,
    UserMessage,
)
from railtracks.llm.content import ToolCalls
from railtracks.llm.message import Attachment, Role
from railtracks.llm.response import Response
from railtracks.prebuilt.guardrails import (
    BlockTextInputGuard,
    BlockTextOutputGuard,
    InputLengthGuard,
    OutputLengthGuard,
    PIIRedactInputGuard,
    PIIRedactOutputGuard,
)
from railtracks.prebuilt.middleware import ConversationMemory, ToolOutputSummarizer

_NOTICE = r"\.content becomes a list of parts in railtracks 1\.9\.0"
_PNG = b"\x89PNG\r\n\x1a\n" + bytes(32)


class _Report(BaseModel):
    summary: str


def _call() -> ToolCall:
    return ToolCall(identifier="c1", name="get_weather", arguments={"city": "Paris"})


pytestmark = pytest.mark.filterwarnings("error::FutureWarning")


@pytest.mark.parametrize(
    ("message", "instead"),
    [
        (UserMessage("Hi"), "Use .text instead"),
        (
            UserMessage("Look", attachment=Attachment.from_bytes(_PNG)),
            "Use .text and .attachments instead",
        ),
        (SystemMessage("Be brief."), "Use .text instead"),
        (AssistantMessage("Hi"), "Use .text instead"),
        (
            AssistantMessage(ToolCalls([_call()], text="Checking.")),
            "Use .tool_calls and .text instead",
        ),
        (
            ToolMessage(
                ToolResponse(identifier="c1", name="get_weather", result="18C")
            ),
            "Use .text, .tool_call_id and .name instead",
        ),
    ],
    ids=["user", "user_attachment", "system", "assistant", "tool_calls", "tool"],
)
def test_reading_message_content_warns_with_its_replacement(message, instead):
    with pytest.warns(FutureWarning, match=_NOTICE) as record:
        _ = message.content
    assert instead in str(record[0].message)
    assert record[0].filename == __file__


def test_reading_string_response_content_warns():
    response = StringResponse("Hi", MessageHistory())
    with pytest.warns(FutureWarning, match=r"StringResponse\.content .* Use \.text"):
        _ = response.content


def test_structured_output_does_not_warn():
    report = _Report(summary="Sunny")
    assert AssistantMessage(report).content is report
    assert StructuredResponse(report, MessageHistory()).content is report


def _reader_in(module: str):
    namespace: dict[str, object] = {"__name__": module}
    exec("def read(message):\n    return message.content", namespace)
    read = namespace["read"]
    assert callable(read)
    return read


@pytest.mark.parametrize("module", ["railtracks", "railtracks.prebuilt.fake"])
def test_reads_from_railtracks_modules_do_not_warn(module):
    assert _reader_in(module)(UserMessage("Hi")) == "Hi"


def test_reads_from_a_lookalike_package_still_warn():
    with pytest.warns(FutureWarning, match=_NOTICE):
        _reader_in("railtracks_app.guards")(UserMessage("Hi"))


class TestForwardReaders:
    def test_text_of_each_message_kind(self):
        assert UserMessage("Hi").text == "Hi"
        assert SystemMessage("Be brief.").text == "Be brief."
        assert AssistantMessage("Hi").text == "Hi"
        assert AssistantMessage(ToolCalls([_call()], text="Checking.")).text == (
            "Checking."
        )
        assert AssistantMessage(ToolCalls([_call()])).text == ""
        assert AssistantMessage(_Report(summary="Sunny")).text == ""

    def test_tool_message_readers(self):
        message = ToolMessage(
            ToolResponse(identifier="c1", name="get_weather", result=b"18\xc2\xb0C")
        )
        assert message.text == "18°C"
        assert message.tool_call_id == "c1"
        assert message.name == "get_weather"
        assert message.attachments == []

    def test_attachments(self):
        image = Attachment.from_bytes(_PNG)
        assert UserMessage("Look", attachment=image).attachments == [image]
        assert UserMessage("Hi").attachments == []
        assert AssistantMessage("Hi").attachments == []

    def test_tool_calls(self):
        assert AssistantMessage(ToolCalls([_call()])).tool_calls == [_call()]
        assert AssistantMessage("Hi").tool_calls == []

    def test_response_text(self):
        assert StringResponse("Hi", MessageHistory()).text == "Hi"
        structured = StructuredResponse(_Report(summary="Sunny"), MessageHistory())
        with pytest.raises(TypeError, match="structured output"):
            _ = structured.text


@pytest.mark.asyncio
async def test_a_full_run_through_railtracks_emits_no_notice(mock_llm):
    def get_weather(city: str) -> str:
        """Get the weather.

        Args:
            city: The city.
        """
        return f"{city}: 18C and sunny. " * 20

    def chat_with_tools(messages, tools):
        if messages[-1].role == Role.tool:
            return Response(message=AssistantMessage("It is sunny in Paris."))
        return Response(
            message=AssistantMessage(ToolCalls([_call()], text="Checking."))
        )

    llm = mock_llm()
    llm._chat_with_tools = chat_with_tools
    agent = rt.agent_node(
        name="Weather",
        tool_nodes=[rt.function_node(get_weather)],
        system_message="Answer about the weather.",
        llm=llm,
        middleware=[ConversationMemory()],
        model_middleware=[
            BlockTextInputGuard(pattern=r"\bjailbreak\b"),
            PIIRedactInputGuard(),
            InputLengthGuard(max_chars=100_000),
            ToolOutputSummarizer(
                mock_llm(custom_response="Sunny."), max_chars=50, summary_max_chars=20
            ),
            BlockTextOutputGuard(pattern=r"\bjailbreak\b"),
            PIIRedactOutputGuard(),
            OutputLengthGuard(max_chars=100_000),
        ],
    )

    result = await rt.Flow("notices", agent).ainvoke("Weather in Paris?")

    assert result.text == "It is sunny in Paris."
    assert [call.name for call, _ in result.tool_invocations] == ["get_weather"]
    assert str(result) == "It is sunny in Paris."
    result.encode()
