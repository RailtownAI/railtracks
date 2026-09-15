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
    GLOBAL_CONVERSATION_STORE,
    ConversationMemory,
)


@pytest.fixture(autouse=True)
def clear_global_store():
    GLOBAL_CONVERSATION_STORE.clear()
    yield
    GLOBAL_CONVERSATION_STORE.clear()


def test_conversation_memory_is_a_plain_middleware():
    assert isinstance(ConversationMemory(), Middleware)


def test_conversation_memory_exported_flat():
    from railtracks.prebuilt.middleware import (
        GLOBAL_CONVERSATION_STORE as PUBLIC_STORE,
    )
    from railtracks.prebuilt.middleware import (
        ConversationMemory as PublicMemory,
    )

    assert PublicMemory is ConversationMemory
    assert PUBLIC_STORE is GLOBAL_CONVERSATION_STORE


@pytest.mark.asyncio
async def test_first_call_stores_response_history():
    custom_store: dict[str, MessageHistory] = {}
    memory = ConversationMemory(store=custom_store)

    async def mock_node(user_input: str):
        history = MessageHistory([UserMessage(user_input), AssistantMessage("Hello!")])
        return StringResponse("Hello!", history)

    wrapped = memory.wrap(mock_node)
    result = await wrapped("Hi there")

    assert result.text == "Hello!"
    assert "default" in custom_store
    assert len(custom_store["default"]) == 2
    assert custom_store["default"][0].content == "Hi there"
    assert custom_store["default"][1].content == "Hello!"


@pytest.mark.asyncio
async def test_subsequent_calls_append_to_history():
    custom_store: dict[str, MessageHistory] = {}
    memory = ConversationMemory(store=custom_store)

    received_inputs: list[object] = []

    async def mock_node(user_input):
        received_inputs.append(user_input)
        if isinstance(user_input, str):
            history = MessageHistory(
                [UserMessage(user_input), AssistantMessage(f"Echo: {user_input}")]
            )
        else:
            # user_input is MessageHistory
            history = MessageHistory([*user_input, AssistantMessage("Second reply")])
        return StringResponse("Reply", history)

    wrapped = memory.wrap(mock_node)

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

    # Check store after turn 2
    assert len(custom_store["default"]) == 4
    assert custom_store["default"][3].content == "Second reply"


@pytest.mark.asyncio
async def test_session_key_isolation():
    custom_store: dict[str, MessageHistory] = {}
    mem_user1 = ConversationMemory(session_key="user_1", store=custom_store)
    mem_user2 = ConversationMemory(session_key="user_2", store=custom_store)

    async def mock_node(user_input: str):
        history = MessageHistory([UserMessage(user_input), AssistantMessage("ack")])
        return StringResponse("ack", history)

    await mem_user1.wrap(mock_node)("Msg 1")
    await mem_user2.wrap(mock_node)("Msg 2")

    assert len(custom_store["user_1"]) == 2
    assert custom_store["user_1"][0].content == "Msg 1"
    assert len(custom_store["user_2"]) == 2
    assert custom_store["user_2"][0].content == "Msg 2"


@pytest.mark.asyncio
async def test_dynamic_callable_session_key():
    current_user = "alice"
    custom_store: dict[str, MessageHistory] = {}
    memory = ConversationMemory(session_key=lambda: current_user, store=custom_store)

    async def mock_node(user_input: str):
        history = MessageHistory([UserMessage(user_input), AssistantMessage("ack")])
        return StringResponse("ack", history)

    wrapped = memory.wrap(mock_node)
    await wrapped("Hello from alice")

    current_user = "bob"
    await wrapped("Hello from bob")

    assert "alice" in custom_store
    assert "bob" in custom_store
    assert custom_store["alice"][0].content == "Hello from alice"
    assert custom_store["bob"][0].content == "Hello from bob"


@pytest.mark.asyncio
async def test_clear_method():
    custom_store: dict[str, MessageHistory] = {}
    memory = ConversationMemory(store=custom_store)

    custom_store["s1"] = MessageHistory([UserMessage("a")])
    custom_store["s2"] = MessageHistory([UserMessage("b")])

    memory.clear("s1")
    assert "s1" not in custom_store
    assert "s2" in custom_store

    memory.clear()
    assert len(custom_store) == 0


@pytest.mark.asyncio
async def test_max_messages_limit():
    custom_store: dict[str, MessageHistory] = {}
    memory = ConversationMemory(store=custom_store, max_messages=2)

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
    await wrapped("input")

    # Stored history should be trimmed to the last 2 messages
    assert len(custom_store["default"]) == 2
    assert custom_store["default"][0].content == "3"
    assert custom_store["default"][1].content == "4"


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
    custom_store: dict[str, MessageHistory] = {}
    memory = ConversationMemory(store=custom_store)

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
async def test_uses_global_store_by_default_and_supports_kwargs():
    memory = ConversationMemory()  # Uses GLOBAL_CONVERSATION_STORE

    async def mock_node(user_input):
        if isinstance(user_input, str):
            history = MessageHistory(
                [UserMessage(user_input), AssistantMessage(f"Echo: {user_input}")]
            )
        else:
            history = MessageHistory([*user_input, AssistantMessage("Echo")])
        return StringResponse("Reply", history)

    wrapped = memory.wrap(mock_node)

    # Call with keyword argument
    await wrapped(user_input="First message")
    assert "default" in GLOBAL_CONVERSATION_STORE
    assert len(GLOBAL_CONVERSATION_STORE["default"]) == 2

    # Second call with keyword argument
    await wrapped(user_input="Second message")
    assert len(GLOBAL_CONVERSATION_STORE["default"]) == 4


def test_sync_flow_invoke_with_conversation_memory():
    fake_model = _FakeEchoModel()
    custom_store: dict[str, MessageHistory] = {}
    memory = ConversationMemory(store=custom_store)

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
