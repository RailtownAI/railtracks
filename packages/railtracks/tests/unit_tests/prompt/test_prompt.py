import asyncio

import pytest
import railtracks as rt
from railtracks.llm import Message, MessageHistory
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
