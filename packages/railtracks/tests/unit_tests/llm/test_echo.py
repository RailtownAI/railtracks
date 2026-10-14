import socket
from collections.abc import AsyncIterable

import pytest
import railtracks as rt
from pydantic import BaseModel
from railtracks.exceptions import LLMError
from railtracks.llm import (
    AssistantMessage,
    EchoLLM,
    MessageHistory,
    ModelProvider,
    Response,
    SystemMessage,
    ToolMessage,
    ToolResponse,
    UserMessage,
)

_ECHO_LINE = "This is an echo of the test model."
_SPEC_HISTORY = "system: You are a helper\nuser: hi\nThis is an echo of the test model."


def _history() -> MessageHistory:
    return MessageHistory(
        [
            SystemMessage("You are a helper"),
            UserMessage("hi"),
            AssistantMessage("ok"),
            ToolMessage(ToolResponse(identifier="1", name="add", result="3")),
        ]
    )


def _expected_echo(messages: MessageHistory) -> str:
    lines = [str(message) for message in messages]
    lines.append(_ECHO_LINE)
    return "\n".join(lines)


def test_echo_llm_is_exported_from_railtracks_llm():
    model = rt.llm.EchoLLM()
    assert isinstance(model, EchoLLM)
    assert "EchoLLM" in rt.llm.__all__


def test_identity_and_zero_usage():
    model = EchoLLM()
    response = model.chat(
        MessageHistory([SystemMessage("You are a helper"), UserMessage("hi")])
    )

    assert model.model_name() == "echo"
    assert model.model_provider() is ModelProvider.UNKNOWN
    assert model.model_gateway() is ModelProvider.UNKNOWN
    assert response.message.role == "assistant"
    assert response.message.content == _SPEC_HISTORY
    info = response.message_info
    assert info.input_tokens == 0
    assert info.output_tokens == 0
    assert info.total_tokens == 0
    assert info.total_cost == 0
    assert info.latency == 0
    assert info.model_name == "echo"


def test_chat_echoes_every_role():
    messages = _history()
    response = EchoLLM().chat(messages)
    assert response.message.content == (
        "system: You are a helper\n"
        "user: hi\n"
        "assistant: ok\n"
        "tool: add -> 3\n"
        "This is an echo of the test model."
    )
    assert response.message.content == _expected_echo(messages)


def test_empty_history_is_only_the_echo_line():
    response = EchoLLM().chat(MessageHistory())
    assert response.message.content == _ECHO_LINE


def test_chat_with_tools_never_requests_a_tool():
    messages = _history()
    tool = rt.llm.Tool("add", "Add two numbers.", None)
    response = EchoLLM().chat_with_tools(messages, [tool])

    assert response.message.content == _expected_echo(messages)
    assert response.message.tool_calls == []


async def test_async_methods_match_sync():
    model = EchoLLM()
    messages = _history()
    tool = rt.llm.Tool("add", "Add two numbers.", None)

    chat = await model.achat(messages)
    with_tools = await model.achat_with_tools(messages, [tool])

    assert chat.message.content == model.chat(messages).message.content
    assert (
        with_tools.message.content
        == model.chat_with_tools(messages, [tool]).message.content
    )
    assert chat.message_info.model_name == "echo"
    assert chat.message_info.input_tokens == 0
    assert chat.message_info.output_tokens == 0
    assert chat.message_info.total_cost == 0


def test_structured_output_raises():
    model = EchoLLM()
    messages = MessageHistory([UserMessage("hi")])

    class Answer(BaseModel):
        text: str

    with pytest.raises(
        NotImplementedError, match="EchoLLM does not support structured output"
    ):
        model.structured(messages, Answer)


async def test_astructured_output_raises():
    model = EchoLLM()
    messages = MessageHistory([UserMessage("hi")])

    class Answer(BaseModel):
        text: str

    with pytest.raises(
        NotImplementedError, match="EchoLLM does not support structured output"
    ):
        await model.astructured(messages, Answer)


def test_call_needs_no_api_key_or_network(monkeypatch):
    for name in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "AZURE_API_KEY",
        "HUGGINGFACE_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)

    def fail_connect(*args, **kwargs):
        raise AssertionError(f"EchoLLM opened a connection: {args!r} {kwargs!r}")

    monkeypatch.setattr(socket, "create_connection", fail_connect)
    monkeypatch.setattr(socket.socket, "connect", fail_connect)

    model = EchoLLM()
    response = model.chat(MessageHistory([UserMessage("hi")]))
    assert response.message.content == f"user: hi\n{_ECHO_LINE}"


@rt.function_node
def add(a: int, b: int) -> int:
    """Add two numbers.

    Args:
        a: The first number.
        b: The second number.

    Returns:
        The sum.
    """
    return a + b


def test_flow_invoke_without_tools():
    agent = rt.agent_node(
        llm=rt.llm.EchoLLM(),
        system_message="You are a helper",
    )
    result = rt.Flow("echo without tools", entry_point=agent).invoke("hi")
    assert result.content == _SPEC_HISTORY
    assert result.tool_invocations == []


async def test_flow_ainvoke_without_tools():
    agent = rt.agent_node(
        llm=rt.llm.EchoLLM(),
        system_message="You are a helper",
    )
    result = await rt.Flow("echo without tools async", entry_point=agent).ainvoke("hi")
    assert result.content == _SPEC_HISTORY


def test_flow_invoke_with_tools_finishes_in_one_turn():
    agent = rt.agent_node(
        llm=rt.llm.EchoLLM(),
        system_message="You are a helper",
        tool_nodes=[add],
    )
    result = rt.Flow("echo with tools", entry_point=agent).invoke("hi")
    assert result.content == _SPEC_HISTORY
    assert result.tool_invocations == []


async def test_flow_ainvoke_with_tools_finishes_in_one_turn():
    agent = rt.agent_node(
        llm=rt.llm.EchoLLM(),
        system_message="You are a helper",
        tool_nodes=[add],
    )
    result = await rt.Flow("echo with tools async", entry_point=agent).ainvoke("hi")
    assert result.content == _SPEC_HISTORY
    assert result.tool_invocations == []


def test_flow_structured_output_raises():
    class Answer(BaseModel):
        text: str

    agent = rt.agent_node(
        llm=rt.llm.EchoLLM(),
        system_message="You are a helper",
        output_schema=Answer,
    )
    with pytest.raises(LLMError, match="EchoLLM does not support structured output"):
        rt.Flow("echo structured", entry_point=agent).invoke("hi")


def _record_sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("railtracks.llm.models.testing.echo.asyncio.sleep", fake_sleep)
    return sleeps


async def _collect(
    stream: AsyncIterable[str | Response],
) -> tuple[list[str], Response]:
    chunks: list[str] = []
    final: Response | None = None
    async for item in stream:
        if isinstance(item, str):
            assert final is None
            chunks.append(item)
        else:
            assert isinstance(item, Response)
            assert final is None
            final = item
    assert final is not None
    return chunks, final


def _assert_even_chunks(chunks: list[str], content: str) -> None:
    assert len(chunks) == 5
    assert "".join(chunks) == content
    sizes = [len(chunk) for chunk in chunks]
    assert max(sizes) - min(sizes) <= 1
    assert sizes == sorted(sizes, reverse=True)


async def test_astream_chat_yields_five_chunks_then_the_chat_response(monkeypatch):
    sleeps = _record_sleeps(monkeypatch)
    model = EchoLLM()
    messages = _history()
    chat = model.chat(messages)

    chunks, final = await _collect(model.astream_chat(messages))

    _assert_even_chunks(chunks, chat.message.content)
    assert sleeps == [1.0, 1.0, 1.0, 1.0, 1.0]
    assert sum(sleeps) == 5
    assert final.message.content == chat.message.content
    assert final.message.tool_calls == []
    assert final.message_info.input_tokens == 0
    assert final.message_info.output_tokens == 0
    assert final.message_info.total_tokens == 0
    assert final.message_info.total_cost == 0
    assert final.message_info.latency == 0
    assert final.message_info.model_name == "echo"


async def test_astream_chat_with_tools_matches_chat_and_requests_nothing(monkeypatch):
    sleeps = _record_sleeps(monkeypatch)
    model = EchoLLM()
    messages = _history()
    tool = rt.llm.Tool("add", "Add two numbers.", None)
    chat = model.chat_with_tools(messages, [tool])

    chunks, final = await _collect(model.astream_chat_with_tools(messages, [tool]))

    _assert_even_chunks(chunks, chat.message.content)
    assert sum(sleeps) == 5
    assert final.message.content == chat.message.content
    assert final.message.tool_calls == []
    assert final.message_info.input_tokens == 0
    assert final.message_info.output_tokens == 0
    assert final.message_info.latency == 0
    assert final.message_info.model_name == "echo"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", ["", "", "", "", ""]),
        ("a", ["a", "", "", "", ""]),
        ("abcd", ["a", "b", "c", "d", ""]),
        ("abcde", ["a", "b", "c", "d", "e"]),
        ("abcdef", ["ab", "c", "d", "e", "f"]),
        ("ab\ncd", ["a", "b", "\n", "c", "d"]),
        ("123456789012", ["123", "456", "78", "90", "12"]),
        ("🙂🙂", ["🙂", "🙂", "", "", ""]),
    ],
)
async def test_astream_chat_splits_short_and_uneven_text(
    monkeypatch: pytest.MonkeyPatch, text: str, expected: list[str]
) -> None:
    sleeps = _record_sleeps(monkeypatch)
    model = EchoLLM()
    sent = Response(
        message=AssistantMessage(text),
        message_info=model._message_info(),
    )

    def fake_echo(self, messages: MessageHistory) -> Response:
        return sent

    monkeypatch.setattr(EchoLLM, "_echo", fake_echo)

    chunks, final = await _collect(
        model.astream_chat(MessageHistory([UserMessage("hi")]))
    )

    assert chunks == expected
    assert "".join(chunks) == sent.message.content
    assert final is sent
    assert sleeps == [1.0] * 5
    assert sum(sleeps) == 5


async def test_astream_structured_raises():
    model = EchoLLM()
    messages = MessageHistory([UserMessage("hi")])

    class Answer(BaseModel):
        text: str

    with pytest.raises(
        NotImplementedError,
        match="EchoLLM does not support streamed structured calls",
    ):
        async for _item in model.astream_structured(messages, Answer):
            pass


async def test_rt_astream_without_tools(monkeypatch):
    _record_sleeps(monkeypatch)
    agent = rt.agent_node(
        llm=rt.llm.EchoLLM(),
        system_message="You are a helper",
    )
    stream = rt.astream(agent, user_input="hi")
    chunks = [chunk async for chunk in stream]

    _assert_even_chunks(chunks, _SPEC_HISTORY)
    assert stream.result.content == _SPEC_HISTORY
    assert stream.result.text == _SPEC_HISTORY
    assert stream.result.tool_invocations == []


async def test_rt_astream_with_tools(monkeypatch):
    _record_sleeps(monkeypatch)
    agent = rt.agent_node(
        llm=rt.llm.EchoLLM(),
        system_message="You are a helper",
        tool_nodes=[add],
    )
    stream = rt.astream(agent, user_input="hi")
    chunks = [chunk async for chunk in stream]

    _assert_even_chunks(chunks, _SPEC_HISTORY)
    assert "".join(chunks) == stream.result.content
    assert stream.result.tool_invocations == []
