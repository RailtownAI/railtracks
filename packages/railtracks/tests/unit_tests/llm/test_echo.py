import socket

import pytest
import railtracks as rt
from pydantic import BaseModel
from railtracks.exceptions import LLMError
from railtracks.llm import (
    AssistantMessage,
    EchoLLM,
    MessageHistory,
    ModelProvider,
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
