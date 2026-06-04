import asyncio

import pytest
import railtracks as rt
from railtracks.built_nodes.concrete.terminal_llm_base import TerminalLLM
from railtracks.llm import Message, MessageHistory, UserMessage
from railtracks.llm.response import Response
from railtracks.llm.message import Role


def test_prompt_injection(mock_llm):
    prompt = "{secret}"

    def return_message(messages: MessageHistory) -> Response:
        return Response(message=Message(role=Role.assistant, content=messages[-1].content))

    model = mock_llm()
    model._chat = return_message

    node = rt.agent_node(system_message=prompt, llm=model)

    async def top_level():
        with rt.Session(context={"secret": "tomato"}):
            response = await rt.call(node, user_input=MessageHistory())
        return response

    response = asyncio.run(top_level())
    assert response.content == "tomato"


def test_prompt_injection_bypass(mock_llm):
    prompt = "{{secret_value}}"

    def return_message(messages: MessageHistory) -> Response:
        return Response(message=Message(role=Role.assistant, content=messages[-1].content))

    model = mock_llm()
    model._chat = return_message

    node = rt.agent_node(system_message=prompt, llm=model)

    async def top_level():
        with rt.Session(context={"secret_value": "tomato"}):
            response = await rt.call(node, user_input=MessageHistory())
        return response

    response = asyncio.run(top_level())

    assert response.content == "{secret_value}"


def test_prompt_numerical(mock_llm):
    prompt = "{1}"

    def return_message(messages: MessageHistory) -> Response:
        return Response(message=Message(role=Role.assistant, content=messages[-1].content))

    model = mock_llm()
    model._chat = return_message

    node = rt.agent_node(
        system_message=prompt,
        llm=model
    )

    async def top_level():
        with rt.Session(context={"1": "tomato"}):
            response = await rt.call(node, user_input=MessageHistory())
        return response

    response = asyncio.run(top_level())

    assert response.content == "tomato"


def test_prompt_not_in_context(mock_llm):
    prompt = "{secret2}"

    def return_message(messages: MessageHistory) -> Response:
        return Response(message=Message(role=Role.assistant, content=messages[-1].content))

    model = mock_llm()
    model._chat = return_message

    node = rt.agent_node(
        system_message=prompt,
        llm=model
    )

    async def top_level():
        with rt.Session():
            response = await rt.call(node, user_input=MessageHistory())

        return response

    response = asyncio.run(top_level())

    assert response.content == "{secret2}"


def test_prompt_injection_llm_level_bypass(mock_llm):
    prompt = "{secret_value}"

    def return_message(messages: MessageHistory) -> Response:
        return Response(message=Message(role=Role.assistant, content=messages[-1].content))

    model = mock_llm()
    model._chat = return_message

    node = rt.agent_node(
        system_message=prompt,
        llm=model,
        context_injection=False,
    )

    async def top_level():
        with rt.Session(context={"secret_value": "tomato"}):
            response = await rt.call(node, user_input=MessageHistory())

        return response

    response = asyncio.run(top_level())
    assert response.content == "{secret_value}"


def test_prompt_injection_class_based_bypass(mock_llm):
    """Class-based API: subclass with context_injection = False skips injection."""
    prompt = "{secret_value}"

    def return_message(messages: MessageHistory) -> Response:
        return Response(message=Message(role=Role.assistant, content=messages[-1].content))

    model = mock_llm()
    model._chat = return_message

    class MyAgent(TerminalLLM):
        context_injection = False

        @classmethod
        def system_message(cls):
            return rt.llm.SystemMessage(prompt)

        @classmethod
        def get_llm(cls):
            return model

    async def top_level():
        with rt.Session(context={"secret_value": "tomato"}):
            response = await rt.call(MyAgent, user_input=MessageHistory())
        return response

    response = asyncio.run(top_level())
    assert response.content == "{secret_value}"


def test_prompt_injection_message_level_bypass(mock_llm):
    """Message-level inject_prompt=False leaves that message's placeholders untouched."""

    def return_message(messages: MessageHistory) -> Response:
        # Return the user message content (last non-system message before assistant)
        user_content = next(
            m.content for m in reversed(messages) if m.role == "user"
        )
        return Response(message=Message(role=Role.assistant, content=user_content))

    model = mock_llm()
    model._chat = return_message

    node = rt.agent_node(llm=model)

    async def top_level():
        with rt.Session(context={"topic": "Python"}):
            user_msg = UserMessage("{topic}", inject_prompt=False)
            response = await rt.call(node, user_input=MessageHistory([user_msg]))
        return response

    response = asyncio.run(top_level())
    assert response.content == "{topic}"


@pytest.mark.order("last")
def test_prompt_injection_global_config_bypass(mock_llm):
    prompt = "{secret_value}"

    def return_message(messages: MessageHistory) -> Response:
        return Response(message=Message(role=Role.assistant, content=messages[-1].content))

    model = mock_llm()
    model._chat = return_message

    node = rt.agent_node(
        system_message=prompt,
        llm=model
    )

    async def top_level():
        with rt.Session(context={"secret_value": "tomato"}, prompt_injection=False):
            response = await rt.call(node, user_input=MessageHistory())

        return response

    response = asyncio.run(top_level())
    assert response.content == "{secret_value}"
