import pytest

from railtracks.llm import MessageHistory, Message
from railtracks.llm.response import Response
import railtracks as rt


def test_prompt_injection(mock_llm):
    prompt = "{secret}"

    async def return_message(messages: MessageHistory) -> Response:
        return Response(message=Message(role="assistant", content=messages[-1].content))

    model = mock_llm()
    model._achat = return_message

    node = rt.agent_node(
        system_message=prompt,
        llm_model=model
    )

    with rt.Session(context={"secret": "tomato"}) as runner:
        response = rt.call_sync(node, user_input=MessageHistory())

    assert response.content == "tomato"


def test_prompt_injection_bypass(mock_llm):
    prompt = "{{secret_value}}"

    async def return_message(messages: MessageHistory) -> Response:
        return Response(message=Message(role="assistant", content=messages[-1].content))

    model = mock_llm()
    model._achat = return_message

    node = rt.agent_node(
        system_message=prompt,
        llm_model=model
    )

    with rt.Session(context={"secret_value": "tomato"}) as runner:
        response = rt.call_sync(node, user_input=MessageHistory())

    assert response.content == "{secret_value}"


def test_prompt_numerical(mock_llm):
    prompt = "{1}"

    async def return_message(messages: MessageHistory) -> Response:
        return Response(message=Message(role="assistant", content=messages[-1].content))

    model = mock_llm()
    model._achat = return_message

    node = rt.agent_node(
        system_message=prompt,
        llm_model=model
    )

    with rt.Session(context={"1": "tomato"}) as runner:
        response = rt.call_sync(node, user_input=MessageHistory())

    assert response.content == "tomato"


def test_prompt_not_in_context(mock_llm):
    prompt = "{secret2}"

    async def return_message(messages: MessageHistory) -> Response:
        return Response(message=Message(role="assistant", content=messages[-1].content))

    model = mock_llm()
    model._achat = return_message

    node = rt.agent_node(
        system_message=prompt,
        llm_model=model
    )

    with rt.Session() as runner:
        response = rt.call_sync(node, user_input=MessageHistory())

    assert response.content == "{secret2}"


@pytest.mark.order("last")
def test_prompt_injection_global_config_bypass(mock_llm):
    prompt = "{secret_value}"

    async def return_message(messages: MessageHistory) -> Response:
        return Response(message=Message(role="assistant", content=messages[-1].content))

    model = mock_llm()
    model._achat = return_message

    node = rt.agent_node(
        system_message=prompt,
        llm_model=model
    )

    with rt.Session(
            context={"secret_value": "tomato"},
            prompt_injection=False
    ) as runner:
        response = rt.call_sync(node, user_input=MessageHistory())

    assert response.content == "{secret_value}"
