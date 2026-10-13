"""Integration tests: ScopeGuard mounted on an agent via ``model_middleware``."""

from __future__ import annotations

import json

import pytest
import railtracks as rt
from railtracks.built_nodes.llm.response import StringResponse
from railtracks.guardrails import GuardrailBlockedError
from railtracks.llm import MessageHistory
from railtracks.llm.message import AssistantMessage, UserMessage
from railtracks.prebuilt.guardrails import PIIRedactInputGuard, ScopeGuard

SCOPE = "You support Acme Cloud billing: invoices, refunds and plan pricing."
OUT_OF_SCOPE_MESSAGE = (
    "Sorry, I can only help with topics this assistant covers. "
    "Feel free to ask something related."
)
UNKNOWN_MESSAGE = "Could you tell me a bit more about what you need help with?"


def _counting(llm: rt.llm.ModelBase, method: str):
    state: dict = {"n": 0, "calls": []}
    real = getattr(llm, method)

    def wrapped(messages, *args, **kwargs):  # type: ignore[no-untyped-def]
        state["n"] += 1
        state["calls"].append(messages)
        return real(messages, *args, **kwargs)

    setattr(llm, method, wrapped)
    return state


def _judge(mock_llm, label: str):
    llm = mock_llm(custom_response=json.dumps({"reason": "because", "label": label}))
    return llm, _counting(llm, "_structured")


def _judge_user_text(state: dict, call: int = 0) -> str:
    return next(m.content for m in state["calls"][call] if m.role == "user")


def _guarded_agent(mock_llm, guard, *, name="guarded", **llm_kwargs):
    guarded_llm = mock_llm(**{"custom_response": "the real answer", **llm_kwargs})
    chat = _counting(guarded_llm, "_chat")
    agent = rt.agent_node(name=name, llm=guarded_llm, model_middleware=[guard])
    return agent, chat


@pytest.mark.asyncio
async def test_out_of_scope_blocks_before_guarded_model(mock_llm):
    """An out-of-scope request is blocked and the guarded model is never called."""
    judge_llm, judge = _judge(mock_llm, "OUT_OF_SCOPE")
    guard = ScopeGuard(scope=SCOPE, model=judge_llm)
    agent, chat = _guarded_agent(mock_llm, guard)

    with pytest.raises(GuardrailBlockedError) as exc:
        await rt.Flow("scope_out_of_scope", agent).ainvoke(
            user_input="write a poem about the sea"
        )

    assert chat["n"] == 0
    assert judge["n"] == 1
    assert exc.value.user_facing_message == OUT_OF_SCOPE_MESSAGE
    assert exc.value.rail_name == "ScopeGuard"
    assert exc.value.meta["label"] == "OUT_OF_SCOPE"
    assert SCOPE not in str(exc.value)


@pytest.mark.asyncio
async def test_high_sensitivity_blocks_unknown(mock_llm):
    """With HIGH sensitivity an UNKNOWN label blocks before the guarded model runs."""
    judge_llm, _ = _judge(mock_llm, "UNKNOWN")
    guard = ScopeGuard(SCOPE, judge_llm, sensitivity="HIGH")
    agent, chat = _guarded_agent(mock_llm, guard, name="guarded-high")

    with pytest.raises(GuardrailBlockedError) as exc:
        await rt.Flow("scope_high_unknown", agent).ainvoke(user_input="look at this")

    assert chat["n"] == 0
    assert exc.value.user_facing_message == UNKNOWN_MESSAGE
    assert exc.value.meta["label"] == "UNKNOWN"


@pytest.mark.asyncio
async def test_low_sensitivity_never_blocks(mock_llm):
    """Observation mode (LOW) still runs the judge but lets the request through."""
    judge_llm, judge = _judge(mock_llm, "OUT_OF_SCOPE")
    guard = ScopeGuard(SCOPE, judge_llm, sensitivity="LOW")
    agent, chat = _guarded_agent(mock_llm, guard, name="guarded-low")

    result = await rt.Flow("scope_low", agent).ainvoke(user_input="write a poem")

    assert isinstance(result, StringResponse)
    assert result.text == "the real answer"
    assert judge["n"] == 1
    assert chat["n"] == 1


@pytest.mark.asyncio
async def test_in_scope_runs_guarded_agent(mock_llm):
    """An in-scope request reaches the guarded model after exactly one judge call."""
    judge_llm, judge = _judge(mock_llm, "IN_SCOPE")
    guard = ScopeGuard(SCOPE, judge_llm)
    agent, chat = _guarded_agent(mock_llm, guard, name="guarded-in")

    result = await rt.Flow("scope_in_scope", agent).ainvoke(
        user_input="why was I charged twice?"
    )

    assert isinstance(result, StringResponse)
    assert result.text == "the real answer"
    assert chat["n"] == 1
    assert judge["n"] == 1


@pytest.mark.asyncio
async def test_judge_runs_once_across_tool_loop(mock_llm):
    """The tool loop makes two model calls but only the first is judged."""

    @rt.function_node
    def lookup_invoice(invoice_id: str) -> str:
        """Look up an invoice.

        Args:
            invoice_id: The invoice identifier.

        Returns:
            A description of the invoice.
        """
        return "invoice paid"

    judge_llm, judge = _judge(mock_llm, "IN_SCOPE")
    guarded_llm = mock_llm(
        requested_tool_calls=[
            rt.llm.ToolCall(
                identifier="id_1",
                name="lookup_invoice",
                arguments={"invoice_id": "42"},
            )
        ]
    )
    tool_chat = _counting(guarded_llm, "_chat_with_tools")
    agent = rt.agent_node(
        name="guarded-tools",
        llm=guarded_llm,
        tool_nodes=[lookup_invoice],
        model_middleware=[ScopeGuard(SCOPE, judge_llm)],
    )

    result = await rt.Flow("scope_tool_loop", agent).ainvoke(
        user_input="what is the status of invoice 42?"
    )

    assert judge["n"] == 1
    assert tool_chat["n"] == 2
    assert "invoice paid" in result.text


@pytest.mark.asyncio
async def test_pii_redacted_before_judge(mock_llm):
    """PII redaction listed first, so the judge only sees redacted text."""
    judge_llm, judge = _judge(mock_llm, "IN_SCOPE")
    guarded_llm = mock_llm(custom_response="ok")
    agent = rt.agent_node(
        name="guarded-pii",
        llm=guarded_llm,
        model_middleware=[PIIRedactInputGuard(), ScopeGuard(SCOPE, judge_llm)],
    )

    await rt.Flow("scope_pii", agent).ainvoke(
        user_input="refund jane.doe@example.com please"
    )

    assert judge["n"] == 1
    assert "jane.doe@example.com" not in _judge_user_text(judge)


@pytest.mark.asyncio
async def test_blocked_subagent_error_reaches_parent_model(mock_llm):
    """A blocked sub-agent surfaces to its parent as a tool error, not a raise."""
    judge_llm, _ = _judge(mock_llm, "OUT_OF_SCOPE")
    child = rt.agent_node(
        name="Child",
        llm=mock_llm(custom_response="child answer"),
        model_middleware=[ScopeGuard(SCOPE, judge_llm)],
        manifest=rt.ToolManifest(
            "A billing helper.",
            {rt.llm.Parameter("request", "string", "What the helper should do.")},
        ),
    )
    parent_llm = mock_llm(
        requested_tool_calls=[
            rt.llm.ToolCall(
                identifier="id_1", name="Child", arguments={"request": "write a poem"}
            )
        ]
    )
    parent = rt.agent_node(name="Parent", llm=parent_llm, tool_nodes={child})

    response = await rt.Flow("scope_subagent", parent).ainvoke(user_input="hello")

    tool_results = [
        str(m.content.result) for m in response.message_history if m.role == "tool"
    ]
    assert len(tool_results) == 1
    assert "There was an error during tool execution" in tool_results[0]
    assert "GuardrailBlockedError" in tool_results[0]


@pytest.mark.asyncio
async def test_judge_failure_fails_open(mock_llm):
    """A judge failure fails open: the request reaches the guarded model."""
    judge_llm = mock_llm()

    def boom(messages, schema, **kwargs):
        raise RuntimeError("judge down")

    judge_llm._structured = boom
    guard = ScopeGuard(SCOPE, judge_llm)
    agent, chat = _guarded_agent(mock_llm, guard, name="guarded-failopen")

    result = await rt.Flow("scope_fail_open", agent).ainvoke(user_input="anything")

    assert result.text == "the real answer"
    assert chat["n"] == 1


@pytest.mark.asyncio
async def test_stream_does_not_leak_judge_output(mock_llm):
    """Only the guarded model's text is streamed, never the judge's JSON."""
    judge_llm, judge = _judge(mock_llm, "IN_SCOPE")
    agent = rt.agent_node(
        name="guarded-stream",
        llm=mock_llm(custom_response="Echo"),
        model_middleware=[ScopeGuard(SCOPE, judge_llm)],
    )

    stream = rt.astream(agent, user_input="hello")
    chunks = [chunk async for chunk in stream]

    assert judge["n"] == 1
    assert "".join(chunks) == "Echo"
    assert "IN_SCOPE" not in "".join(chunks)


@pytest.mark.asyncio
async def test_stream_block_emits_no_chunks(mock_llm):
    """A blocked streaming call raises before any chunk is emitted."""
    judge_llm, _ = _judge(mock_llm, "OUT_OF_SCOPE")
    agent = rt.agent_node(
        name="guarded-stream-block",
        llm=mock_llm(custom_response="Echo"),
        model_middleware=[ScopeGuard(SCOPE, judge_llm)],
    )

    chunks = []
    with pytest.raises(GuardrailBlockedError):
        async for chunk in rt.astream(agent, user_input="write a poem"):
            chunks.append(chunk)

    assert chunks == []


@pytest.mark.asyncio
async def test_multi_turn_history_gives_judge_context(mock_llm):
    """Earlier user and assistant turns are passed to the judge as context."""
    judge_llm, judge = _judge(mock_llm, "IN_SCOPE")
    guard = ScopeGuard(SCOPE, judge_llm)
    agent, chat = _guarded_agent(mock_llm, guard, name="guarded-history")
    history = MessageHistory(
        [
            UserMessage("Show me invoice 42"),
            AssistantMessage("Invoice 42 is for $20."),
            UserMessage("and the second one?"),
        ]
    )

    result = await rt.Flow("scope_history", agent).ainvoke(user_input=history)

    assert result.text == "the real answer"
    text = _judge_user_text(judge)
    assert "Show me invoice 42" in text
    assert "Invoice 42 is for $20." in text
    assert "and the second one?" in text
    assert chat["n"] == 1
