"""Tests for the ModelSource contract: an agent accepts either a concrete model
or a no-arg factory, resolved fresh on every model call (runtime model swap)."""

import asyncio

import railtracks as rt
from railtracks.llm import Message, MessageHistory
from railtracks.llm.message import Role
from railtracks.llm.response import Response


def _echo_last_message(messages: MessageHistory) -> Response:
    return Response(message=Message(role=Role.assistant, content=messages[-1].content))


def test_agent_node_accepts_model_factory(mock_llm):
    model = mock_llm()
    model._chat = _echo_last_message

    node = rt.agent_node(system_message="hello", llm=lambda: model)

    async def top_level():
        with rt.Session():
            return await rt.call(node, user_input=MessageHistory())

    response = asyncio.run(top_level())
    assert response.content == "hello"


def test_model_factory_resolved_per_call(mock_llm):
    """The factory is consulted on every call, so swapping the model it returns
    swaps the model used by an already-built node."""
    model_a = mock_llm()
    model_a._chat = lambda messages: Response(
        message=Message(role=Role.assistant, content="from-a")
    )
    model_b = mock_llm()
    model_b._chat = lambda messages: Response(
        message=Message(role=Role.assistant, content="from-b")
    )

    current = {"model": model_a}
    node = rt.agent_node(system_message="hi", llm=lambda: current["model"])

    async def run_once():
        with rt.Session():
            return await rt.call(node, user_input=MessageHistory())

    assert asyncio.run(run_once()).content == "from-a"
    current["model"] = model_b
    assert asyncio.run(run_once()).content == "from-b"
