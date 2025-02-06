import concurrent.futures
import random

import pytest

from src.requestcompletionn.llm import (
    ModelBase,
    AssistantMessage,
    MessageHistory,
    UserMessage,
    SystemMessage,
    Tool,
    ToolCall,
)

from typing import Type, List

from src.requestcompletion.llm.response import Response
from tests.rc_tests.llm.fixtures import MockLLM


def test_simple_message():
    hello_world = "Hello world"
    model = MockLLM(chat=lambda x: Response(AssistantMessage(hello_world)))
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


def test_simple_message_2():
    hello_world = "Hello World"
    model = MockLLM(chat=lambda x: Response(AssistantMessage(hello_world)))
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


def test_conversation_message():
    hello_world = "Hello World"
    model = MockLLM(chat=lambda x: Response(AssistantMessage(hello_world)))
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


def test_tool_call():
    identifier = "9282hejeh"

    def tool_call(mess_hist: MessageHistory, tool_calls: List[Tool]):
        tool = random.choice(tool_calls)

        return Response(
            AssistantMessage(
                [ToolCall(identifier=identifier, name=tool.name, arguments={})]
            )
        )

    model = MockLLM(chat_with_tools=tool_call)

    tool_name = "tool1"
    tool_description = "Call this tool sometime"
    response = model.chat_with_tools(
        MessageHistory(),
        [Tool(tool_name, tool_description, [])],
    )

    assert response.message.content[0].identifier == identifier
    assert response.message.content[0].name == tool_name
    assert response.message.content[0].arguments == {}


def test_multiple_tool_calls():
    identifier = "9282hejeh"

    def tool_call(mess_hist: MessageHistory, tool_calls: List[Tool]):
        tool = random.choice(tool_calls)

        return Response(
            AssistantMessage(
                [ToolCall(identifier=identifier, name=tool.name, arguments={})]
            )
        )

    model = MockLLM(chat_with_tools=tool_call)

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


def test_many_calls_in_parallel():
    identifier = "9282hejeh"

    def tool_call(mess_hist: MessageHistory, tool_calls: List[Tool]):
        tool = random.choice(tool_calls)

        return Response(
            AssistantMessage(
                [ToolCall(identifier=identifier, name=tool.name, arguments={})]
            )
        )

    model = MockLLM(chat_with_tools=tool_call)

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
