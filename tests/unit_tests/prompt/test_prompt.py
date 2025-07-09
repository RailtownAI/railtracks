import pytest

from requestcompletion import ExecutorConfig
from requestcompletion.llm import MessageHistory, Message
from requestcompletion.llm.response import Response
from requestcompletion.nodes.library.easy_usage_wrappers.terminal_llm import terminal_llm
from tests.unit_tests.llm.conftest import MockLLM
import requestcompletion as rc


def test_prompt_injection():
    prompt = "{secret}"

    def return_message(messages: MessageHistory) -> Response:
        return Response(message=Message(role="assistant", content=messages[-1].content))

    node = terminal_llm(
        system_message=prompt,
        model=MockLLM(chat=return_message)
    )

    with rc.Runner(context={"secret": "tomato"}) as runner:
        response = runner.run_sync(node, message_history=MessageHistory())

    assert response.answer == "tomato"


def test_prompt_injection_bypass():
    prompt = "{{secret_value}}"

    def return_message(messages: MessageHistory) -> Response:
        return Response(message=Message(role="assistant", content=messages[-1].content))

    node = terminal_llm(
        system_message=prompt,
        model=MockLLM(chat=return_message)
    )

    with rc.Runner(context={"secret_value": "tomato"}) as runner:
        response = runner.run_sync(node, message_history=MessageHistory())

    assert response.answer == "{secret_value}"


def test_prompt_numerical():
    prompt = "{1}"

    def return_message(messages: MessageHistory) -> Response:
        return Response(message=Message(role="assistant", content=messages[-1].content))

    node = terminal_llm(
        system_message=prompt,
        model=MockLLM(chat=return_message)
    )

    with rc.Runner(context={"1": "tomato"}) as runner:
        response = runner.run_sync(node, message_history=MessageHistory())

    assert response.answer == "tomato"


def test_prompt_not_in_context():
    prompt = "{secret2}"

    def return_message(messages: MessageHistory) -> Response:
        return Response(message=Message(role="assistant", content=messages[-1].content))

    node = terminal_llm(
        system_message=prompt,
        model=MockLLM(chat=return_message)
    )

    with rc.Runner() as runner:
        response = runner.run_sync(node, message_history=MessageHistory())

    assert response.answer == "{secret2}"


@pytest.mark.order("last")
def test_prompt_injection_global_config_bypass():
    prompt = "{secret_value}"

    def return_message(messages: MessageHistory) -> Response:
        return Response(message=Message(role="assistant", content=messages[-1].content))

    node = terminal_llm(
        system_message=prompt,
        model=MockLLM(chat=return_message)
    )

    with rc.Runner(
            context={"secret_value": "tomato"},
            executor_config=ExecutorConfig(prompt_injection=False)
    ) as runner:
        response = runner.run_sync(node, message_history=MessageHistory())

    assert response.answer == "{secret_value}"
