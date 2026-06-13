import asyncio

import pytest
import railtracks as rt
from railtracks.llm import Message, MessageHistory
from railtracks.llm.message import Role
from railtracks.llm.response import Response


def test_prompt_injection(mock_llm):
    prompt = "{secret}"

    def return_message(messages: MessageHistory) -> Response:
        return Response(
            message=Message(role=Role.assistant, content=messages[-1].content)
        )

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
        return Response(
            message=Message(role=Role.assistant, content=messages[-1].content)
        )

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
        return Response(
            message=Message(role=Role.assistant, content=messages[-1].content)
        )

    model = mock_llm()
    model._chat = return_message

    node = rt.agent_node(system_message=prompt, llm=model)

    async def top_level():
        with rt.Session(context={"1": "tomato"}):
            response = await rt.call(node, user_input=MessageHistory())
        return response

    response = asyncio.run(top_level())

    assert response.content == "tomato"


def test_prompt_not_in_context(mock_llm):
    prompt = "{secret2}"

    def return_message(messages: MessageHistory) -> Response:
        return Response(
            message=Message(role=Role.assistant, content=messages[-1].content)
        )

    model = mock_llm()
    model._chat = return_message

    node = rt.agent_node(system_message=prompt, llm=model)

    async def top_level():
        with rt.Session():
            response = await rt.call(node, user_input=MessageHistory())

        return response

    response = asyncio.run(top_level())

    assert response.content == "{secret2}"


def test_prompt_injection_node_level_bypass(mock_llm):
    prompt = "{secret_value}"

    def return_message(messages: MessageHistory) -> Response:
        return Response(
            message=Message(role=Role.assistant, content=messages[-1].content)
        )

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


def test_prompt_injection_shared_middleware_list_stays_independent(mock_llm):
    """Regression: one user middleware list reused across nodes must not be mutated
    by the system context-injection gateway, and per-node context_injection flags
    must act independently even with the shared list."""
    prompt = "{secret_value}"

    def return_message(messages: MessageHistory) -> Response:
        return Response(
            message=Message(role=Role.assistant, content=messages[-1].content)
        )

    model_on = mock_llm()
    model_on._chat = return_message
    model_off = mock_llm()
    model_off._chat = return_message

    shared_middleware = []

    node_on = rt.agent_node(
        system_message=prompt,
        llm=model_on,
        model_middleware=shared_middleware,
    )
    node_off = rt.agent_node(
        system_message=prompt,
        llm=model_off,
        model_middleware=shared_middleware,
        context_injection=False,
    )

    async def top_level():
        with rt.Session(context={"secret_value": "tomato"}):
            on = await rt.call(node_on, user_input=MessageHistory())
            off = await rt.call(node_off, user_input=MessageHistory())
        return on, off

    on, off = asyncio.run(top_level())
    assert on.content == "tomato"
    assert off.content == "{secret_value}"
    assert shared_middleware == []


@pytest.mark.order("last")
def test_prompt_injection_global_config_bypass(mock_llm):
    prompt = "{secret_value}"

    def return_message(messages: MessageHistory) -> Response:
        return Response(
            message=Message(role=Role.assistant, content=messages[-1].content)
        )

    model = mock_llm()
    model._chat = return_message

    node = rt.agent_node(system_message=prompt, llm=model)

    async def top_level():
        with rt.Session(context={"secret_value": "tomato"}, prompt_injection=False):
            response = await rt.call(node, user_input=MessageHistory())

        return response

    response = asyncio.run(top_level())
    assert response.content == "{secret_value}"
