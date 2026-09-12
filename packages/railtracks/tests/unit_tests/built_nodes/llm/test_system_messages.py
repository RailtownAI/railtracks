"""Semantics for system messages: which ones the framework owns, which ones belong to the caller,
and what survives a round trip through an agent's response. See
https://docs.railtracks.org/documentation/agent_design/llms/system_messages/.
"""

from __future__ import annotations

import pytest
import railtracks.built_nodes.llm.llm_helpers as llm_helpers
from railtracks.built_nodes.llm.llm_helpers import (
    append_system_message,
    prepare_message_history,
)
from railtracks.exceptions import NodeInvocationError
from railtracks.llm.history import MessageHistory
from railtracks.llm.message import (
    AssistantMessage,
    Role,
    SystemMessage,
    UserMessage,
    _AgentSystemMessage,
)
from railtracks.llm.response import Response
from railtracks.validation.node_invocation.validation import check_message_history


def _kinds(history: MessageHistory) -> list[str]:
    """The class name of every message, so agent-owned and caller-owned system turns differ."""
    return [type(m).__name__ for m in history]


def _invoker_returning(content: str):
    """A stand-in ModelInvoker whose `invoke` always answers with `content`."""

    class _StaticInvoker:
        @classmethod
        def create_with_llm_observe(cls, *args, **kwargs):
            return cls()

        async def invoke(self, *args, **kwargs):
            return Response(message=AssistantMessage(content))

    return _StaticInvoker


class _FakeNode:
    _user_model_middleware = []
    _scope_manager = None


# ---------------------------------------------------------------------------
# prepare_message_history
# ---------------------------------------------------------------------------


def test_agent_system_message_is_placed_first():
    prepared = prepare_message_history(SystemMessage("agent"), "hi")

    assert _kinds(prepared) == ["_AgentSystemMessage", "UserMessage"]
    assert prepared[0].content == "agent"


def test_caller_system_message_is_left_where_it_is():
    history = MessageHistory([SystemMessage("caller"), UserMessage("hi")])

    prepared = prepare_message_history(None, history)

    assert _kinds(prepared) == ["SystemMessage", "UserMessage"]


def test_agent_system_message_precedes_a_caller_system_message():
    history = MessageHistory([SystemMessage("caller"), UserMessage("hi")])

    prepared = prepare_message_history(SystemMessage("agent"), history)

    assert _kinds(prepared) == ["_AgentSystemMessage", "SystemMessage", "UserMessage"]
    assert [m.content for m in prepared] == ["agent", "caller", "hi"]


def test_several_caller_system_messages_keep_their_order():
    history = MessageHistory(
        [SystemMessage("first"), SystemMessage("second"), UserMessage("hi")]
    )

    prepared = prepare_message_history(None, history)

    assert [m.content for m in prepared] == ["first", "second", "hi"]


def test_the_callers_history_is_not_modified():
    history = MessageHistory([SystemMessage("caller"), UserMessage("hi")])

    prepare_message_history(SystemMessage("agent"), history)

    assert _kinds(history) == ["SystemMessage", "UserMessage"]


def test_each_call_gets_its_own_copy_of_the_agent_system_message():
    system_message = SystemMessage("agent")

    first = prepare_message_history(system_message, "hi")
    second = prepare_message_history(system_message, "hi again")

    assert first[0] is not second[0]
    assert first[0] is not system_message


# ---------------------------------------------------------------------------
# append_system_message
# ---------------------------------------------------------------------------


def test_append_system_message_replaces_an_existing_agent_message():
    history = MessageHistory([_AgentSystemMessage("stale"), UserMessage("hi")])

    append_system_message(history, SystemMessage("fresh"))

    assert _kinds(history) == ["_AgentSystemMessage", "UserMessage"]
    assert history[0].content == "fresh"


def test_append_system_message_drops_a_stale_agent_message_when_given_none():
    history = MessageHistory([_AgentSystemMessage("stale"), UserMessage("hi")])

    append_system_message(history, None)

    assert _kinds(history) == ["UserMessage"]


# ---------------------------------------------------------------------------
# the response path
# ---------------------------------------------------------------------------


async def test_returned_history_hides_the_agents_own_system_message(monkeypatch):
    monkeypatch.setattr(llm_helpers, "ModelInvoker", _invoker_returning("answer"))
    invoke = llm_helpers.llm_invoke_factory(object(), SystemMessage("agent"))

    response = await invoke(_FakeNode(), "hi")

    assert _kinds(response.message_history) == ["UserMessage", "AssistantMessage"]


async def test_returned_history_keeps_a_caller_system_message(monkeypatch):
    """The bug behind #1350: a caller's prompt used to be stripped out of the response."""
    monkeypatch.setattr(llm_helpers, "ModelInvoker", _invoker_returning("answer"))
    invoke = llm_helpers.llm_invoke_factory(object(), None)
    history = MessageHistory([SystemMessage("caller"), UserMessage("hi")])

    response = await invoke(_FakeNode(), history)

    assert _kinds(response.message_history) == [
        "SystemMessage",
        "UserMessage",
        "AssistantMessage",
    ]
    assert response.message_history[0].content == "caller"


async def test_a_caller_system_message_survives_repeated_turns(monkeypatch):
    monkeypatch.setattr(llm_helpers, "ModelInvoker", _invoker_returning("answer"))
    invoke = llm_helpers.llm_invoke_factory(object(), None)
    history = MessageHistory([SystemMessage("caller"), UserMessage("hi")])

    for _ in range(3):
        history = (await invoke(_FakeNode(), history)).message_history
        history.append(UserMessage("again"))

    assert sum(1 for m in history if m.role == Role.system) == 1
    assert history[0].content == "caller"


async def test_the_agent_prompt_does_not_accumulate_across_turns(monkeypatch):
    """Feeding a response back to its own agent re-sends one prompt, not one per turn."""
    monkeypatch.setattr(llm_helpers, "ModelInvoker", _invoker_returning("answer"))
    sent: list[MessageHistory] = []

    async def _record(self, message_history, **kwargs):
        sent.append(MessageHistory(list(message_history)))
        return Response(message=AssistantMessage("answer"))

    invoker = _invoker_returning("answer")
    monkeypatch.setattr(invoker, "invoke", _record)
    monkeypatch.setattr(llm_helpers, "ModelInvoker", invoker)
    invoke = llm_helpers.llm_invoke_factory(object(), SystemMessage("agent"))

    history: MessageHistory | str = "hi"
    for _ in range(3):
        history = (await invoke(_FakeNode(), history)).message_history
        history.append(UserMessage("again"))

    assert [sum(1 for m in h if m.role == Role.system) for h in sent] == [1, 1, 1]
    assert all(isinstance(h[0], _AgentSystemMessage) for h in sent)


# ---------------------------------------------------------------------------
# check_message_history
# ---------------------------------------------------------------------------


def test_empty_history_is_fatal():
    with pytest.raises(NodeInvocationError) as exc:
        check_message_history(MessageHistory([]))

    assert exc.value.fatal is True


def test_non_message_entry_is_fatal():
    with pytest.raises(NodeInvocationError) as exc:
        check_message_history(MessageHistory(["not a message"]))

    assert exc.value.fatal is True


def test_history_without_any_system_message_warns(caplog):
    check_message_history(MessageHistory([UserMessage("hi")]))

    assert "No SystemMessage" in caplog.text


def test_a_system_message_anywhere_suppresses_the_missing_prompt_warning(caplog):
    history = MessageHistory(
        [UserMessage("hi"), AssistantMessage("hello"), SystemMessage("late")]
    )

    check_message_history(history)

    assert "No SystemMessage" not in caplog.text


def test_history_of_only_system_messages_warns(caplog):
    check_message_history(MessageHistory([SystemMessage("a"), SystemMessage("b")]))

    assert "Only SystemMessage" in caplog.text


def test_a_mid_conversation_system_message_warns(caplog):
    history = MessageHistory(
        [SystemMessage("lead"), UserMessage("hi"), SystemMessage("late")]
    )

    check_message_history(history)

    assert "after a non-system message" in caplog.text


def test_leading_system_messages_do_not_warn(caplog):
    history = MessageHistory(
        [SystemMessage("a"), SystemMessage("b"), UserMessage("hi")]
    )

    check_message_history(history)

    assert caplog.text == ""


def test_the_agents_own_system_message_counts_as_a_leading_one(caplog):
    history = MessageHistory(
        [_AgentSystemMessage("agent"), SystemMessage("caller"), UserMessage("hi")]
    )

    check_message_history(history)

    assert caplog.text == ""
