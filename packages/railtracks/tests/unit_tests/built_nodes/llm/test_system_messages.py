"""Semantics for system messages: what reaches the model, what comes back to the caller, and
what the validator warns about. See
https://docs.railtracks.org/documentation/agent_design/llms/system_messages/.
"""

from __future__ import annotations

import pytest
import railtracks.built_nodes.llm.llm_helpers as llm_helpers
from railtracks.built_nodes.llm.llm_helpers import _wire_history
from railtracks.exceptions import LLMError, NodeInvocationError
from railtracks.llm.content import ToolCall, ToolCalls, ToolResponse
from railtracks.llm.history import MessageHistory
from railtracks.llm.message import (
    AssistantMessage,
    Role,
    SystemMessage,
    ToolMessage,
    UserMessage,
)
from railtracks.llm.response import Response
from railtracks.validation.node_invocation.validation import check_message_history


def _contents(history: MessageHistory) -> list[str]:
    return [str(m.content) for m in history]


def _roles(history: MessageHistory) -> list[str]:
    return [m.role.value for m in history]


class _FakeNode:
    _user_model_middleware = []
    _scope_manager = None


def _recording_invoker(*responses: Response):
    """A stand-in ModelInvoker that records each history it is handed.

    Answers with `responses` in turn, repeating the last one once they run out.
    """
    sent: list[MessageHistory] = []

    class _Invoker:
        @classmethod
        def create_with_llm_observe(cls, *args, **kwargs):
            return cls()

        async def invoke(self, message_history, **kwargs):
            sent.append(MessageHistory(list(message_history)))
            return responses[min(len(sent) - 1, len(responses) - 1)]

    return _Invoker, sent


def _answer(text: str = "answer") -> Response:
    return Response(message=AssistantMessage(text))


def _tool_request() -> Response:
    call = ToolCall(identifier="1", name="a_tool", arguments={})
    return Response(message=AssistantMessage(ToolCalls([call])))


def _tool_result() -> ToolResponse:
    return ToolResponse(identifier="1", name="a_tool", result="tool result")


# ---------------------------------------------------------------------------
# what reaches the model
# ---------------------------------------------------------------------------


def test_the_agent_system_message_goes_first():
    conversation = MessageHistory([UserMessage("hi")])

    wire = _wire_history(SystemMessage("agent"), conversation)

    assert _contents(wire) == ["agent", "hi"]


def test_a_caller_system_message_keeps_its_place():
    conversation = MessageHistory([SystemMessage("caller"), UserMessage("hi")])

    wire = _wire_history(SystemMessage("agent"), conversation)

    assert _contents(wire) == ["agent", "caller", "hi"]


def test_several_caller_system_messages_keep_their_order():
    conversation = MessageHistory(
        [SystemMessage("first"), SystemMessage("second"), UserMessage("hi")]
    )

    wire = _wire_history(None, conversation)

    assert _contents(wire) == ["first", "second", "hi"]


def test_building_the_wire_leaves_the_conversation_alone():
    conversation = MessageHistory([UserMessage("hi")])

    _wire_history(SystemMessage("agent"), conversation)

    assert _contents(conversation) == ["hi"]


def test_each_wire_carries_its_own_copy_of_the_agent_system_message():
    """Prompt injection fills templates in place, so the shared node-level message is copied."""
    system_message = SystemMessage("You are helping {user_name}.")
    conversation = MessageHistory([UserMessage("hi")])

    first = _wire_history(system_message, conversation)
    second = _wire_history(system_message, conversation)

    assert first[0] is not second[0]
    assert first[0] is not system_message


def test_structural_edits_to_a_wire_do_not_reach_the_conversation():
    conversation = MessageHistory([UserMessage("hi")])

    wire = _wire_history(None, conversation)
    wire.append(UserMessage("added by middleware"))

    assert _contents(conversation) == ["hi"]


# ---------------------------------------------------------------------------
# what comes back to the caller
# ---------------------------------------------------------------------------


async def test_the_agent_system_message_stays_out_of_the_returned_history(monkeypatch):
    invoker, sent = _recording_invoker(_answer())
    monkeypatch.setattr(llm_helpers, "ModelInvoker", invoker)
    invoke = llm_helpers.llm_invoke_factory(object(), SystemMessage("agent"))

    response = await invoke(_FakeNode(), "hi")

    assert _contents(sent[0]) == ["agent", "hi"]
    assert _contents(response.message_history) == ["hi", "answer"]


async def test_a_caller_system_message_comes_back(monkeypatch):
    """The bug behind #1350: a caller's prompt used to be stripped out of the response."""
    invoker, _ = _recording_invoker(_answer())
    monkeypatch.setattr(llm_helpers, "ModelInvoker", invoker)
    invoke = llm_helpers.llm_invoke_factory(object(), None)
    history = MessageHistory([SystemMessage("caller"), UserMessage("hi")])

    response = await invoke(_FakeNode(), history)

    assert _roles(response.message_history) == ["system", "user", "assistant"]
    assert response.message_history[0].content == "caller"


async def test_a_caller_system_message_survives_repeated_turns(monkeypatch):
    invoker, _ = _recording_invoker(_answer())
    monkeypatch.setattr(llm_helpers, "ModelInvoker", invoker)
    invoke = llm_helpers.llm_invoke_factory(object(), None)
    history = MessageHistory([SystemMessage("caller"), UserMessage("hi")])

    for _ in range(3):
        history = (await invoke(_FakeNode(), history)).message_history
        history.append(UserMessage("again"))

    assert sum(1 for m in history if m.role == Role.system) == 1
    assert history[0].content == "caller"


async def test_the_agent_system_message_does_not_accumulate(monkeypatch):
    """Feeding a response back to its own agent sends one prompt, not one per turn."""
    invoker, sent = _recording_invoker(_answer())
    monkeypatch.setattr(llm_helpers, "ModelInvoker", invoker)
    invoke = llm_helpers.llm_invoke_factory(object(), SystemMessage("agent"))

    history = "hi"
    for _ in range(3):
        history = (await invoke(_FakeNode(), history)).message_history
        history.append(UserMessage("again"))

    assert [sum(1 for m in h if m.role == Role.system) for h in sent] == [1, 1, 1]
    assert all(h[0].content == "agent" for h in sent)


async def test_the_callers_own_history_object_is_not_modified(monkeypatch):
    invoker, _ = _recording_invoker(_answer())
    monkeypatch.setattr(llm_helpers, "ModelInvoker", invoker)
    invoke = llm_helpers.llm_invoke_factory(object(), SystemMessage("agent"))
    history = MessageHistory([UserMessage("hi")])

    await invoke(_FakeNode(), history)

    assert _contents(history) == ["hi"]


# ---------------------------------------------------------------------------
# the tool-calling loop
# ---------------------------------------------------------------------------


async def test_every_model_call_in_the_loop_carries_the_agent_message(monkeypatch):
    invoker, sent = _recording_invoker(_tool_request(), _answer())
    monkeypatch.setattr(llm_helpers, "ModelInvoker", invoker)

    async def _fake_run_tools(response, message_history, tool_nodes):
        message_history.append(ToolMessage(_tool_result()))

    monkeypatch.setattr(llm_helpers, "run_tools", _fake_run_tools)
    invoke = llm_helpers.llm_invoke_factory(object(), SystemMessage("agent"))

    response = await invoke(_FakeNode(), "hi")

    assert [h[0].content for h in sent] == ["agent", "agent"]
    assert sum(1 for m in sent[1] if m.role == Role.system) == 1
    assert "agent" not in _contents(response.message_history)


async def test_the_history_is_validated_once_per_invocation(monkeypatch):
    invoker, _ = _recording_invoker(_tool_request(), _answer())
    monkeypatch.setattr(llm_helpers, "ModelInvoker", invoker)

    async def _fake_run_tools(response, message_history, tool_nodes):
        message_history.append(ToolMessage(_tool_result()))

    monkeypatch.setattr(llm_helpers, "run_tools", _fake_run_tools)

    calls = []
    monkeypatch.setattr(llm_helpers, "check_message_history", calls.append)
    invoke = llm_helpers.llm_invoke_factory(object(), SystemMessage("agent"))

    await invoke(_FakeNode(), "hi")

    assert len(calls) == 1


# ---------------------------------------------------------------------------
# errors
# ---------------------------------------------------------------------------


async def test_an_error_reports_the_history_that_was_sent(monkeypatch):
    """Errors surface what actually went to the model, agent system message included."""

    class _Exploding:
        @classmethod
        def create_with_llm_observe(cls, *args, **kwargs):
            return cls()

        async def invoke(self, *args, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr(llm_helpers, "ModelInvoker", _Exploding)
    invoke = llm_helpers.llm_invoke_factory(object(), SystemMessage("agent"))

    with pytest.raises(LLMError) as exc:
        await invoke(_FakeNode(), "hi")

    assert _contents(exc.value.message_history) == ["agent", "hi"]


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
