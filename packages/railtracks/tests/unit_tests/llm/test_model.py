import concurrent.futures
import random


from railtracks.llm import (
    AssistantMessage,
    MessageHistory,
    UserMessage,
    SystemMessage,
    Tool,
    ToolCall,
)

from typing import List

from railtracks.llm.response import Response



# ======================================================= START Mock LLM + Messages Testing ========================================================
def test_simple_message(mock_llm):
    hello_world = "Hello world"
    model = mock_llm(custom_response_message=AssistantMessage(hello_world))
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

    model = mock_llm(AssistantMessage(hello_world))
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
    model = mock_llm(AssistantMessage(hello_world))
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

    model = mock_llm(AssistantMessage(hello_world))
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
    model = mock_llm(AssistantMessage(hello_world))
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
    model = mock_llm(AssistantMessage(hello_world))
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

    def tool_call_message(tool_calls: List[Tool]):
        tool = random.choice(tool_calls)

        return AssistantMessage(
                [ToolCall(identifier=identifier, name=tool.name, arguments={})]
            )
    
    tool_name = "tool1"
    tool_description = "Call this tool sometime"
    tool = Tool(tool_name, tool_description, None)

    model = mock_llm(tool_call_message(tool_calls=[tool]))

    response = model.chat_with_tools(
        MessageHistory(),
        [tool],
    )

    assert (
        str(Tool(tool_name, tool_description, None))
        == "Tool(name=tool1, detail=Call this tool sometime, parameters=None)"
    )
    assert response.message.content[0].identifier == identifier
    assert response.message.content[0].name == tool_name
    assert response.message.content[0].arguments == {}


def test_multiple_tool_calls(mock_llm):
    identifier = "9282hejeh"

    def tool_call_message(tool_calls: List[Tool]):
        tool = random.choice(tool_calls)

        return AssistantMessage(
                [ToolCall(identifier=identifier, name=tool.name, arguments={})]
            )

    tool_names = [f"tool{i}" for i in range(2)]
    tool_descriptions = ["Call this tool sometime"] * 2
    tools = []
    for name, description in zip(tool_names, tool_descriptions):
        tools.append(Tool(name, description, {}))
    
    model = mock_llm(tool_call_message(tool_calls=tools))

    for _ in range(10):
        response = model.chat_with_tools(
            MessageHistory(),
            tools,
        )

        assert response.message.content[0].identifier == identifier
        assert response.message.content[0].name in tool_names
        assert response.message.content[0].arguments == {}


def test_many_calls_in_parallel(mock_llm):
    identifier = "9282hejeh"

    def tool_call_message(tool_calls: List[Tool]):
        tool = random.choice(tool_calls)

        return AssistantMessage(
                [ToolCall(identifier=identifier, name=tool.name, arguments={})]
            )

    tool_names = [f"tool{i}" for i in range(10)]
    tool_descriptions = ["Call this tool sometime"] * 10
    tools = []
    for name, description in zip(tool_names, tool_descriptions):
        tools.append(Tool(name, description, {}))
    
    model = mock_llm(tool_call_message(tool_calls=tools))

    with concurrent.futures.ThreadPoolExecutor() as e:

        def func():
            response = model.chat_with_tools(
                MessageHistory(),
                tools,
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