import asyncio

import pytest
import railtracks as rt
from railtracks.llm import Message, MessageHistory
from railtracks.llm.message import Role
from railtracks.llm.response import Response

# Context injection is opt-in: agents only substitute {placeholders} when
# rt.prebuilt.middleware.ContextInjection() is present in model_middleware.


def _return_message(messages: MessageHistory) -> Response:
    return Response(message=Message(role=Role.assistant, content=messages[-1].content))


def test_prompt_injection(mock_llm):
    prompt = "{secret}"

    model = mock_llm()
    model._chat = _return_message

    node = rt.agent_node(
        system_message=prompt,
        llm=model,
        model_middleware=[rt.prebuilt.middleware.ContextInjection()],
    )

    async def top_level():
        with rt.Session(context={"secret": "tomato"}):
            response = await rt.call(node, user_input=MessageHistory())
        return response

    response = asyncio.run(top_level())
    assert response.content == "tomato"


def test_prompt_injection_bypass(mock_llm):
    prompt = "{{secret_value}}"

    model = mock_llm()
    model._chat = _return_message

    node = rt.agent_node(
        system_message=prompt,
        llm=model,
        model_middleware=[rt.prebuilt.middleware.ContextInjection()],
    )

    async def top_level():
        with rt.Session(context={"secret_value": "tomato"}):
            response = await rt.call(node, user_input=MessageHistory())
        return response

    response = asyncio.run(top_level())

    assert response.content == "{secret_value}"


def test_prompt_numerical(mock_llm):
    prompt = "{1}"

    model = mock_llm()
    model._chat = _return_message

    node = rt.agent_node(
        system_message=prompt,
        llm=model,
        model_middleware=[rt.prebuilt.middleware.ContextInjection()],
    )

    async def top_level():
        with rt.Session(context={"1": "tomato"}):
            response = await rt.call(node, user_input=MessageHistory())
        return response

    response = asyncio.run(top_level())

    assert response.content == "tomato"


def test_prompt_not_in_context(mock_llm):
    prompt = "{secret2}"

    model = mock_llm()
    model._chat = _return_message

    node = rt.agent_node(
        system_message=prompt,
        llm=model,
        model_middleware=[rt.prebuilt.middleware.ContextInjection()],
    )

    async def top_level():
        with rt.Session():
            response = await rt.call(node, user_input=MessageHistory())

        return response

    response = asyncio.run(top_level())

    assert response.content == "{secret2}"


def test_no_injection_without_middleware(mock_llm):
    """Without a ContextInjection entry, {placeholders} pass through verbatim."""
    prompt = "{secret_value}"

    model = mock_llm()
    model._chat = _return_message

    node = rt.agent_node(
        system_message=prompt,
        llm=model,
    )

    async def top_level():
        with rt.Session(context={"secret_value": "tomato"}):
            response = await rt.call(node, user_input=MessageHistory())

        return response

    response = asyncio.run(top_level())
    assert response.content == "{secret_value}"


def test_prompt_injection_shared_middleware_list_stays_independent(mock_llm):
    """Regression: one user middleware list reused across nodes must not be mutated
    by node construction, and injection applies only to nodes whose list actually
    contains a ContextInjection entry."""
    prompt = "{secret_value}"

    model_on = mock_llm()
    model_on._chat = _return_message
    model_off = mock_llm()
    model_off._chat = _return_message

    shared_middleware = [rt.prebuilt.middleware.ContextInjection()]

    node_on = rt.agent_node(
        system_message=prompt,
        llm=model_on,
        model_middleware=shared_middleware,
    )
    node_off = rt.agent_node(
        system_message=prompt,
        llm=model_off,
        model_middleware=[],
    )

    async def top_level():
        with rt.Session(context={"secret_value": "tomato"}):
            on = await rt.call(node_on, user_input=MessageHistory())
            off = await rt.call(node_off, user_input=MessageHistory())
        return on, off

    on, off = asyncio.run(top_level())
    assert on.content == "tomato"
    assert off.content == "{secret_value}"
    assert len(shared_middleware) == 1


@pytest.mark.order("last")
def test_prompt_injection_global_config_bypass(mock_llm):
    """Session-level prompt_injection=False wins even when the middleware is present."""
    prompt = "{secret_value}"

    model = mock_llm()
    model._chat = _return_message

    node = rt.agent_node(
        system_message=prompt,
        llm=model,
        model_middleware=[rt.prebuilt.middleware.ContextInjection()],
    )

    async def top_level():
        with rt.Session(context={"secret_value": "tomato"}, prompt_injection=False):
            response = await rt.call(node, user_input=MessageHistory())

        return response

    response = asyncio.run(top_level())
    assert response.content == "{secret_value}"
