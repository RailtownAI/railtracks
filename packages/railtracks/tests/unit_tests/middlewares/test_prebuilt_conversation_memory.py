"""Unit tests for the prebuilt ConversationMemory middleware."""

from __future__ import annotations

import pytest
import railtracks as rt
from railtracks.built_nodes.llm.response import StringResponse
from railtracks.llm.history import MessageHistory
from railtracks.llm.message import AssistantMessage, Message, Role, UserMessage
from railtracks.llm.response import Response
from railtracks.middleware import Middleware
from railtracks.prebuilt.middleware.conversation_memory import (
    ConversationMemory,
)


def test_conversation_memory_is_a_plain_middleware():
    assert isinstance(ConversationMemory(), Middleware)


def test_conversation_memory_exported_flat_without_global_store():
    import railtracks.prebuilt.middleware as pm
    from railtracks.prebuilt.middleware import (
        ConversationMemory as PublicMemory,
    )

    assert PublicMemory is ConversationMemory
    assert not hasattr(pm, "GLOBAL_CONVERSATION_STORE")


@pytest.mark.asyncio
async def test_first_call_stores_response_history_in_session_context():
    memory = ConversationMemory()

    async def mock_node(user_input: str):
        history = MessageHistory([UserMessage(user_input), AssistantMessage("Hello!")])
        return StringResponse("Hello!", history)

    wrapped = memory.wrap(mock_node)

    with rt.Session() as s:
        result = await wrapped("Hi there")
        assert result.text == "Hello!"

        # Verify history is injected into the session variable
        session_hist = s.context.get("conversation_history")
        assert session_hist is not None
        assert len(session_hist) == 2
        assert session_hist[0].content == "Hi there"
        assert session_hist[1].content == "Hello!"

        # Verify get_history helper returns the session history
        assert memory.get_history() == session_hist


@pytest.mark.asyncio
async def test_subsequent_calls_append_to_history():
    memory = ConversationMemory()
    received_inputs: list[object] = []

    async def mock_node(user_input):
        received_inputs.append(user_input)
        if isinstance(user_input, str):
            history = MessageHistory(
                [UserMessage(user_input), AssistantMessage(f"Echo: {user_input}")]
            )
        else:
            history = MessageHistory([*user_input, AssistantMessage("Second reply")])
        return StringResponse("Reply", history)

    wrapped = memory.wrap(mock_node)

    with rt.Session() as s:
        # Turn 1
        await wrapped("What is your name?")
        assert received_inputs[0] == "What is your name?"

        # Turn 2
        await wrapped("What did I just ask?")
        turn_2_input = received_inputs[1]
        assert isinstance(turn_2_input, MessageHistory)
        assert len(turn_2_input) == 3
        assert turn_2_input[0].content == "What is your name?"
        assert turn_2_input[1].content == "Echo: What is your name?"
        assert turn_2_input[2].content == "What did I just ask?"

        # Check session context after turn 2
        session_hist = s.context.get("conversation_history")
        assert len(session_hist) == 4
        assert session_hist[3].content == "Second reply"


@pytest.mark.asyncio
async def test_custom_context_key():
    memory = ConversationMemory(context_key="my_chat")

    async def mock_node(user_input: str):
        history = MessageHistory([UserMessage(user_input), AssistantMessage("ack")])
        return StringResponse("ack", history)

    wrapped = memory.wrap(mock_node)

    with rt.Session() as s:
        await wrapped("Msg 1")
        assert s.context.get("my_chat") is not None
        assert len(s.context.get("my_chat")) == 2
        assert "conversation_history" not in s.context.keys()


@pytest.mark.asyncio
async def test_preloaded_session_context():
    preloaded = MessageHistory(
        [
            UserMessage("Preloaded question"),
            AssistantMessage("Preloaded answer"),
        ]
    )
    memory = ConversationMemory()
    received_inputs: list[object] = []

    async def mock_node(user_input):
        received_inputs.append(user_input)
        history = MessageHistory([*user_input, AssistantMessage("ack")])
        return StringResponse("ack", history)

    wrapped = memory.wrap(mock_node)

    # Initialize session with preloaded context
    with rt.Session(context={"conversation_history": preloaded}):
        await wrapped("New question")
        first_input = received_inputs[0]
        assert isinstance(first_input, MessageHistory)
        assert len(first_input) == 3
        assert first_input[0].content == "Preloaded question"
        assert first_input[1].content == "Preloaded answer"
        assert first_input[2].content == "New question"


@pytest.mark.asyncio
async def test_clear_method():
    memory = ConversationMemory()

    async def mock_node(user_input: str):
        history = MessageHistory([UserMessage(user_input), AssistantMessage("ack")])
        return StringResponse("ack", history)

    wrapped = memory.wrap(mock_node)

    with rt.Session() as s:
        await wrapped("Hi")
        assert s.context.get("conversation_history") is not None

        memory.clear()
        assert "conversation_history" not in s.context.keys()
        assert memory.get_history() is None


@pytest.mark.asyncio
async def test_max_messages_limit():
    memory = ConversationMemory(max_messages=2)

    async def mock_node(user_input):
        history = MessageHistory(
            [
                UserMessage("1"),
                AssistantMessage("2"),
                UserMessage("3"),
                AssistantMessage("4"),
            ]
        )
        return StringResponse("4", history)

    wrapped = memory.wrap(mock_node)

    with rt.Session() as s:
        await wrapped("input")
        session_hist = s.context.get("conversation_history")
        assert len(session_hist) == 2
        assert session_hist[0].content == "3"
        assert session_hist[1].content == "4"


@pytest.mark.asyncio
async def test_keyword_arguments_support():
    memory = ConversationMemory()

    async def mock_node(user_input):
        if isinstance(user_input, str):
            history = MessageHistory(
                [UserMessage(user_input), AssistantMessage(f"Echo: {user_input}")]
            )
        else:
            history = MessageHistory([*user_input, AssistantMessage("Echo")])
        return StringResponse("Reply", history)

    wrapped = memory.wrap(mock_node)

    with rt.Session() as s:
        await wrapped(user_input="First message")
        assert len(s.context.get("conversation_history")) == 2

        await wrapped(user_input="Second message")
        assert len(s.context.get("conversation_history")) == 4


class _FakeEchoModel:
    def __init__(self):
        self.seen_messages: list[MessageHistory] = []

    def chat(self, messages):
        self.seen_messages.append(MessageHistory(messages))
        last = messages[-1].content
        return Response(
            message=Message(role=Role.assistant, content=f"Processed: {last}")
        )

    id = "fake-echo-model"

    def model_name(self):
        return "fake-echo-model"

    def model_provider(self):
        return "fake-provider"


@pytest.mark.asyncio
async def test_end_to_end_agent_node_with_conversation_memory():
    fake_model = _FakeEchoModel()
    memory = ConversationMemory()

    chat_agent = rt.agent_node(
        "ChatAgent",
        llm=fake_model,
        middleware=[memory],
    )

    flow = rt.Flow("chat-flow", entry_point=chat_agent)

    # Turn 1
    res1 = await flow.ainvoke("What is your name?")
    assert res1.text == "Processed: What is your name?"
    assert len(fake_model.seen_messages[0]) == 1  # UserMessage

    # Turn 2
    res2 = await flow.ainvoke("What did I just ask?")
    assert res2.text == "Processed: What did I just ask?"
    # The second model call should have seen Turn 1's user msg, assistant msg, and Turn 2's user msg
    turn2_messages = fake_model.seen_messages[1]
    assert len(turn2_messages) == 3
    assert turn2_messages[0].content == "What is your name?"
    assert turn2_messages[1].content == "Processed: What is your name?"
    assert turn2_messages[2].content == "What did I just ask?"


@pytest.mark.asyncio
async def test_flow_connection_reaches_injected_session_context():
    fake_model = _FakeEchoModel()
    memory = ConversationMemory()

    chat_agent = rt.agent_node(
        "ChatAgentConn",
        llm=fake_model,
        middleware=[memory],
    )

    flow = rt.Flow("chat-flow-conn", entry_point=chat_agent)
    conn = flow.connect()

    res = await conn.ainvoke("Hello from connection")
    assert res.text == "Processed: Hello from connection"

    # Context is reachable on the FlowConnection as session variable
    hist = conn.context.get("conversation_history")
    assert hist is not None
    assert len(hist) == 2
    assert hist[0].content == "Hello from connection"


def test_sync_flow_invoke_with_conversation_memory():
    fake_model = _FakeEchoModel()
    memory = ConversationMemory()

    sync_chat_agent = rt.agent_node(
        "SyncChatAgent",
        llm=fake_model,
        middleware=[memory],
    )

    flow = rt.Flow("sync-chat-flow", entry_point=sync_chat_agent)

    res1 = flow.invoke("Hello")
    assert res1.text == "Processed: Hello"

    res2 = flow.invoke("World")
    assert res2.text == "Processed: World"
    assert len(fake_model.seen_messages[1]) == 3
