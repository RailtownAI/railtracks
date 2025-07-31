import pytest

from railtracks import ExecutorConfig
from railtracks.llm import MessageHistory, Message
from railtracks.llm.response import Response
from railtracks.nodes.easy_usage_wrappers.helpers import terminal_llm
import railtracks as rt


def test_prompt_injection(mock_llm):
    prompt = "{secret}"

    def return_message(messages: MessageHistory) -> Response:
        return Response(message=Message(role="assistant", content=messages[-1].content))

    node = terminal_llm(
        system_message=prompt,
        llm_model=mock_llm(chat=return_message)
    )

    with rt.Session(context={"secret": "tomato"}) as runner:
        response = runner.run_sync(node, user_input=MessageHistory())

    assert response.answer.content == "tomato"


def test_prompt_injection_bypass(mock_llm):
    prompt = "{{secret_value}}"

    def return_message(messages: MessageHistory) -> Response:
        return Response(message=Message(role="assistant", content=messages[-1].content))

    node = terminal_llm(
        system_message=prompt,
        llm_model=mock_llm(chat=return_message)
    )

    with rt.Session(context={"secret_value": "tomato"}) as runner:
        response = runner.run_sync(node, user_input=MessageHistory())

    assert response.answer.content == "{secret_value}"


def test_prompt_numerical(mock_llm):
    prompt = "{1}"

    def return_message(messages: MessageHistory) -> Response:
        return Response(message=Message(role="assistant", content=messages[-1].content))

    node = terminal_llm(
        system_message=prompt,
        llm_model=mock_llm(chat=return_message)
    )

    with rt.Session(context={"1": "tomato"}) as runner:
        response = runner.run_sync(node, user_input=MessageHistory())

    assert response.answer.content == "tomato"


def test_prompt_not_in_context(mock_llm):
    prompt = "{secret2}"

    def return_message(messages: MessageHistory) -> Response:
        return Response(message=Message(role="assistant", content=messages[-1].content))

    node = terminal_llm(
        system_message=prompt,
        llm_model=mock_llm(chat=return_message)
    )

    with rt.Session() as runner:
        response = runner.run_sync(node, user_input=MessageHistory())

    assert response.answer.content == "{secret2}"


@pytest.mark.order("last")
def test_prompt_injection_global_config_bypass(mock_llm):
    prompt = "{secret_value}"

    def return_message(messages: MessageHistory) -> Response:
        return Response(message=Message(role="assistant", content=messages[-1].content))

    node = terminal_llm(
        system_message=prompt,
        llm_model=mock_llm(chat=return_message)
    )

    with rt.Session(
            context={"secret_value": "tomato"},
            prompt_injection=False
    ) as runner:
        response = runner.run_sync(node, user_input=MessageHistory())

    assert response.answer.content == "{secret_value}"
