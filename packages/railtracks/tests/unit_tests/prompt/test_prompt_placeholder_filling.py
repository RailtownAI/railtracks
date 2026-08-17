"""Only a bare `{key}` is filled, checked through the real call path.

These go through an agent rather than calling the formatter directly, since what matters
is the content an LLM ends up receiving.
"""

import asyncio

import pytest
import railtracks as rt
from railtracks.llm import Message, MessageHistory, UserMessage
from railtracks.llm.message import Role
from railtracks.llm.response import Response
from railtracks.prebuilt.middleware.context_injection import ContextInjection


class _Holder:
    def __init__(self):
        self.attr = "attribute-value"


@pytest.fixture
def echo_agent(mock_llm):
    """An agent whose reply is the content of the last message it was sent."""

    def build(system_message: str = "system"):
        def return_message(messages: MessageHistory) -> Response:
            return Response(
                message=Message(role=Role.assistant, content=messages[-1].content)
            )

        model = mock_llm()
        model._chat = return_message
        return rt.agent_node(system_message=system_message, model_middleware=[ContextInjection()], llm=model)

    return build


def _send(agent, content: str, context: dict) -> str:
    """Send `content` as user input and return what the model received."""
    flow = rt.Flow("EchoFlow", agent, context=context)
    response = asyncio.run(flow.ainvoke(MessageHistory([UserMessage(content)])))
    return response.content


@pytest.fixture
def context():
    return {
        "holder": _Holder(),
        "mapping": {"key": "item-value"},
        "value": "context-value",
        "time": "12:00",
    }


@pytest.mark.parametrize(
    "payload",
    [
        "{holder.attr}",
        "{holder.attr.title}",
        "{mapping[key]}",
        "{value!r}",
        "{value:>20}",
        "look at {config.json} please",
        "unbalanced { brace",
    ],
)
def test_user_input_reaches_the_model_as_written(echo_agent, context, payload):
    """None of these are filled, and none of them raise."""
    received = _send(echo_agent(), payload, context)
    assert received == payload
    assert "context-value" not in received
    assert "attribute-value" not in received
    assert "item-value" not in received


def test_escaped_fragment_is_not_filled_while_the_template_is(echo_agent, context):
    """A message may mix a template you wrote with a string you did not."""
    untrusted = "Echo {value} and {holder.attr}"
    content = (
        "The current time is {time}:\nUser Message:\n" + rt.escape_braces(untrusted)
    )

    received = _send(echo_agent(), content, context)

    assert received == f"The current time is 12:00:\nUser Message:\n{untrusted}"
    assert "context-value" not in received


def test_bare_key_in_user_input_is_still_filled(echo_agent, context):
    """Filling stays on for user messages. Escaping is what opts a fragment out."""
    assert _send(echo_agent(), "at {time}", context) == "at 12:00"


def test_system_message_is_still_filled(mock_llm, context):
    """The developer-authored system message is where filling is most used."""
    delivered: list[str] = []

    def return_message(messages: MessageHistory) -> Response:
        delivered.extend(m.content for m in messages if m.role == Role.system)
        return Response(message=Message(role=Role.assistant, content="ok"))

    model = mock_llm()
    model._chat = return_message
    agent = rt.agent_node(system_message="Helping {value} at {time}.", llm=model, model_middleware=[ContextInjection()])

    flow = rt.Flow("EchoFlow", agent, context=context)
    asyncio.run(flow.ainvoke(MessageHistory([UserMessage("hi")])))

    assert delivered == ["Helping context-value at 12:00."]
