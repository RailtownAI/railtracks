import railtracks as rt
from railtracks.llm import Message, MessageHistory
from railtracks.llm.message import Role
from railtracks.llm.response import Response

# Context injection is opt-in: agents only substitute {placeholders} when
# rt.prebuilt.middleware.ContextInjection() is present in model_middleware.


def _return_message(messages: MessageHistory) -> Response:
    return Response(message=Message(role=Role.assistant, content=messages[-1].content))


def test_context_injection(mock_llm):
    prompt = "{secret}"

    model = mock_llm()
    model._chat = _return_message

    node = rt.agent_node(
        system_message=prompt,
        llm=model,
        model_middleware=[rt.prebuilt.middleware.ContextInjection()],
    )

    response = rt.Flow(
        "test_context_injection", node, context={"secret": "tomato"}
    ).invoke(MessageHistory())
    assert response.content == "tomato"


def test_context_injection_bypass(mock_llm):
    prompt = "{{secret_value}}"

    model = mock_llm()
    model._chat = _return_message

    node = rt.agent_node(
        system_message=prompt,
        llm=model,
        model_middleware=[rt.prebuilt.middleware.ContextInjection()],
    )

    response = rt.Flow(
        "test_context_injection_bypass", node, context={"secret_value": "tomato"}
    ).invoke(MessageHistory())

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

    response = rt.Flow("test_prompt_numerical", node, context={"1": "tomato"}).invoke(
        MessageHistory()
    )

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

    response = rt.Flow("test_prompt_not_in_context", node).invoke(MessageHistory())

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

    response = rt.Flow(
        "test_no_injection_without_middleware",
        node,
        context={"secret_value": "tomato"},
    ).invoke(MessageHistory())
    assert response.content == "{secret_value}"


def test_context_injection_shared_middleware_list_stays_independent(mock_llm):
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

    @rt.function_node
    async def entry(user_input):
        on = await rt.call(node_on, user_input=user_input)
        off = await rt.call(node_off, user_input=user_input)
        return on, off

    on, off = rt.Flow(
        "test_context_injection_shared_middleware_list_stays_independent",
        entry,
        context={"secret_value": "tomato"},
    ).invoke(MessageHistory())
    assert on.content == "tomato"
    assert off.content == "{secret_value}"
    assert len(shared_middleware) == 1
