"""Tests for the ModelSource contract: an agent accepts either a concrete model
or a no-arg factory, resolved fresh on every model call (runtime model swap)."""

import railtracks as rt
from railtracks.llm import Message, MessageHistory
from railtracks.llm.message import Role
from railtracks.llm.response import Response
from railtracks.middleware import wrap_node


def _echo_last_message(messages: MessageHistory) -> Response:
    return Response(message=Message(role=Role.assistant, content=messages[-1].content))


def test_agent_node_accepts_model_factory(mock_llm):
    model = mock_llm()
    model._chat = _echo_last_message

    node = rt.agent_node(system_message="hello", llm=lambda: model)

    @rt.function_node
    async def entry(user_input):
        return await rt.call(node, user_input=user_input)

    response = rt.Flow("test_agent_node_accepts_model_factory", entry).invoke(
        MessageHistory()
    )
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

    @rt.function_node
    async def entry(user_input):
        return await rt.call(node, user_input=user_input)

    flow = rt.Flow("test_model_factory_resolved_per_call", entry)

    assert flow.invoke(MessageHistory()).content == "from-a"
    current["model"] = model_b
    assert flow.invoke(MessageHistory()).content == "from-b"


def test_model_middleware_list_mutation_after_build_does_not_affect_built_agent(
    mock_llm,
):
    """NodeBuilder.llm / ModelInvoker deep-copy the passed model_middleware list at
    build time, so mutating the caller's original list afterward has no effect on an
    already-built agent."""
    calls = []

    @wrap_node
    async def tracer(call, *args, **kwargs):
        calls.append("ran")
        return await call(*args, **kwargs)

    shared = [tracer]
    node = rt.agent_node(
        "MutationNode", llm=mock_llm(custom_response="hi"), model_middleware=shared
    )
    shared.append(tracer)  # mutate after build

    @rt.function_node
    async def entry(user_input):
        return await rt.call(node, user_input=user_input)

    rt.Flow(
        "test_model_middleware_list_mutation_after_build_does_not_affect_built_agent",
        entry,
    ).invoke("hello")
    assert calls == [
        "ran"
    ]  # ran once, not twice -- build-time snapshot was independent


def test_two_agents_built_from_same_model_middleware_list_are_independent(mock_llm):
    calls_a = []

    @wrap_node
    async def tracer_a(call, *args, **kwargs):
        calls_a.append("ran")
        return await call(*args, **kwargs)

    shared = [tracer_a]
    node_a = rt.agent_node(
        "A", llm=mock_llm(custom_response="a"), model_middleware=shared
    )
    shared.clear()  # would remove tracer_a from any invoker sharing the list by reference
    node_b = rt.agent_node(
        "B", llm=mock_llm(custom_response="b"), model_middleware=shared
    )

    @rt.function_node
    async def entry_a(user_input):
        return await rt.call(node_a, user_input=user_input)

    @rt.function_node
    async def entry_b(user_input):
        return await rt.call(node_b, user_input=user_input)

    rt.Flow("independent_agent_a", entry_a).invoke("hi")
    rt.Flow("independent_agent_b", entry_b).invoke("hi")
    assert calls_a == [
        "ran"
    ]  # node_a still ran tracer_a despite the later `shared.clear()`
