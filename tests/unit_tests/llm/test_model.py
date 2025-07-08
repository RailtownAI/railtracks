import concurrent.futures
import random


from requestcompletion.llm import (
    AssistantMessage,
    MessageHistory,
    UserMessage,
    SystemMessage,
    Tool,
    ToolCall,
)

from typing import List

from requestcompletion.llm.response import Response
from tests.unit_tests.execution.test_task import hello_world


# ======================================================= START Mock LLM + Messages Testing ========================================================
def test_simple_message(mock_llm):
    hello_world = "Hello world"
    model = mock_llm(chat=lambda x: Response(AssistantMessage(hello_world)))
    mess_hist = MessageHistory(
        [
            UserMessage(
                "When learning a programming langauge, you are often told to print out a statement. What is this statement?"
            )
        ]
    )
    response = model.chat(mess_hist)

    assert response.message.content == hello_world
    assert response.message.role == "assistant"



def test_simple_message_with_pre_hook(mock_llm):
    hello_world = "Hello world"

    def chat_mock(message_history: MessageHistory):
        for m in message_history:
            assert isinstance(m.content, str)
            assert m.content.islower()

        return Response(AssistantMessage(hello_world))

    model = mock_llm(chat=lambda x: Response(AssistantMessage(hello_world)))
    model.add_pre_hook(lambda x: MessageHistory([UserMessage(m.content.lower()) for m in x]))
    mess_hist = MessageHistory(
        [
            UserMessage(
                "When learning a programming langauge, you are often told to print out a statement. What is this statement?"
            )
        ]
    )
    response = model.chat(mess_hist)
    assert response.message.content == hello_world

def test_simple_message_with_post_hook(mock_llm):
    hello_world = "Hello world"

    def chat_mock(message_history: MessageHistory):
        return Response(AssistantMessage(hello_world))

    model = mock_llm(chat=chat_mock)
    model.add_post_hook(lambda x, y: Response(AssistantMessage(y.message.content.upper())))
    mess_hist = MessageHistory(
        [
            UserMessage(
                "When learning a programming langauge, you are often told to print out a statement. What is this statement?"
            )
        ]
    )
    response = model.chat(mess_hist)

    assert response.message.content == hello_world.upper()

def test_simple_message_with_multiple_post_hook(mock_llm):
    hello_world = "Hello world"

    def chat_mock(message_history: MessageHistory):
        return Response(AssistantMessage(hello_world))

    model = mock_llm(chat=chat_mock)
    model.add_post_hook(lambda x, y: Response(AssistantMessage(y.message.content.upper())))
    model.add_post_hook(lambda x, y: Response(AssistantMessage(y.message.content.lower())))
    mess_hist = MessageHistory(
        [
            UserMessage(
                "When learning a programming langauge, you are often told to print out a statement. What is this statement?"
            )
        ]
    )
    response = model.chat(mess_hist)

    assert response.message.content == hello_world.lower()

def test_simple_message_2(mock_llm):
    hello_world = "Hello World"
    model = mock_llm(chat=lambda x: Response(AssistantMessage(hello_world)))
    mess_hist = MessageHistory(
        [
            SystemMessage("You are a helpful assistant"),
            UserMessage(
                "When learning a programming langauge, you are often told to print out a statement. What is this statement?"
            ),
        ]
    )

    response = model.chat(mess_hist)

    assert response.message.content == hello_world
    assert response.message.role == "assistant"


def test_conversation_message(mock_llm):
    hello_world = "Hello World"
    model = mock_llm(chat=lambda x: Response(AssistantMessage(hello_world)))
    mess_hist = MessageHistory(
        [
            SystemMessage("You are a helpful assistant"),
            UserMessage(
                "When learning a programming langauge, you are often told to print out a statement. What is this statement?"
            ),
            AssistantMessage("hello world"),
            UserMessage("Can you use capitals please"),
        ]
    )

    response = model.chat(mess_hist)

    assert response.message.content == hello_world
    assert response.message.role == "assistant"


def test_tool_call(mock_llm):
    identifier = "9282hejeh"

    def tool_call(mess_hist: MessageHistory, tool_calls: List[Tool]):
        tool = random.choice(tool_calls)

        return Response(
            AssistantMessage(
                [ToolCall(identifier=identifier, name=tool.name, arguments={})]
            )
        )

    model = mock_llm(chat_with_tools=tool_call)

    tool_name = "tool1"
    tool_description = "Call this tool sometime"
    response = model.chat_with_tools(
        MessageHistory(),
        [Tool(tool_name, tool_description, [])],
    )

    assert (
        str(Tool(tool_name, tool_description, []))
        == "Tool(name=tool1, detail=Call this tool sometime, parameters=None)"
    )
    assert response.message.content[0].identifier == identifier
    assert response.message.content[0].name == tool_name
    assert response.message.content[0].arguments == {}


def test_multiple_tool_calls(mock_llm):
    identifier = "9282hejeh"

    def tool_call(mess_hist: MessageHistory, tool_calls: List[Tool]):
        tool = random.choice(tool_calls)

        return Response(
            AssistantMessage(
                [ToolCall(identifier=identifier, name=tool.name, arguments={})]
            )
        )

    model = mock_llm(chat_with_tools=tool_call)

    tool_names = [f"tool{i}" for i in range(2)]
    tool_descriptions = ["Call this tool sometime"] * 2

    for _ in range(10):
        response = model.chat_with_tools(
            MessageHistory(),
            [
                Tool(name, description, [])
                for name, description in zip(tool_names, tool_descriptions)
            ],
        )

        assert response.message.content[0].identifier == identifier
        assert response.message.content[0].name in tool_names
        assert response.message.content[0].arguments == {}


def test_many_calls_in_parallel(mock_llm):
    identifier = "9282hejeh"

    def tool_call(mess_hist: MessageHistory, tool_calls: List[Tool]):
        tool = random.choice(tool_calls)

        return Response(
            AssistantMessage(
                [ToolCall(identifier=identifier, name=tool.name, arguments={})]
            )
        )

    model = mock_llm(chat_with_tools=tool_call)

    tool_names = [f"tool{i}" for i in range(10)]
    tool_descriptions = ["Call this tool sometime"] * 10

    with concurrent.futures.ThreadPoolExecutor() as e:

        def func():
            response = model.chat_with_tools(
                MessageHistory(),
                [
                    Tool(name, description, [])
                    for name, description in zip(tool_names, tool_descriptions)
                ],
            )

            assert response.message.content[0].identifier == identifier
            assert response.message.content[0].name in tool_names
            assert response.message.content[0].arguments == {}

        futures = []
        for _ in range(35):
            f = e.submit(func)

            futures.append(f)

        for f in futures:
            f.result()

# ======================================================= END Mock LLM + Messages Testing ========================================================