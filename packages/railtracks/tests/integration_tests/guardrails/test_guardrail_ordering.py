"""Integration tests for guardrail ordering — the actual question this branch answers:
guardrails have no special/fixed slot, they are plain `model_middleware` entries, so
execution order is entirely determined by list position. These tests exercise real
`agent_node` + `model_middleware` wiring (not the mechanics already covered by
test_base_llm_guardrail_run.py / test_guard_middleware_wiring.py).
"""

from __future__ import annotations

import pytest
import railtracks as rt

from railtracks.built_nodes.llm.middleware import before_llm
from railtracks.guardrails.core import GuardrailBlockedError, GuardrailDecision, InputGuard, LLMGuardrailEvent, OutputGuard
from railtracks.llm import UserMessage


class FnInputGuard(InputGuard):
    def __init__(self, fn, name: str | None = None):
        super().__init__(name=name)
        self._decision_fn = fn

    def __call__(self, event: LLMGuardrailEvent) -> GuardrailDecision:
        return self._decision_fn(event)


class FnOutputGuard(OutputGuard):
    def __init__(self, fn, name: str | None = None):
        super().__init__(name=name)
        self._decision_fn = fn

    def __call__(self, event: LLMGuardrailEvent) -> GuardrailDecision:
        return self._decision_fn(event)


# ---------------------------------------------------------------------------
# INPUT guards: list order == evaluation order (each processes before calling onward)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_input_guards_fire_in_list_order(mock_llm):
    trace = []

    guard_a = FnInputGuard(lambda _e: (trace.append("A"), GuardrailDecision.allow())[1])
    guard_b = FnInputGuard(lambda _e: (trace.append("B"), GuardrailDecision.allow())[1])

    Agent = rt.agent_node(
        name="order-input",
        llm=mock_llm(custom_response="ok"),
        model_middleware=[guard_a, guard_b],
    )
    with rt.Session():
        await rt.call(Agent, user_input="hi")

    assert trace == ["A", "B"]


@pytest.mark.asyncio
async def test_input_guard_transform_is_seen_by_the_next_guard_in_the_chain(mock_llm):
    seen = {}

    def redact(event: LLMGuardrailEvent) -> GuardrailDecision:
        new_hist = event.messages.__class__(
            [UserMessage(m.content.replace("secret", "[REDACTED]")) for m in event.messages]
        )
        return GuardrailDecision.transform_messages(messages=new_hist, reason="redact")

    def record(event: LLMGuardrailEvent) -> GuardrailDecision:
        seen["last_content"] = event.messages[-1].content
        return GuardrailDecision.allow()

    Agent = rt.agent_node(
        name="chain-transform",
        llm=mock_llm(custom_response="ok"),
        model_middleware=[FnInputGuard(redact), FnInputGuard(record)],
    )
    with rt.Session():
        await rt.call(Agent, user_input="my secret is X")

    assert seen["last_content"] == "my [REDACTED] is X"


@pytest.mark.asyncio
async def test_input_guard_block_short_circuits_later_guards_in_the_list(mock_llm):
    counts = {"n": 0}

    def count_and_allow(_e):
        counts["n"] += 1
        return GuardrailDecision.allow()

    block = FnInputGuard(lambda _e: GuardrailDecision.block(reason="stop"))
    counter = FnInputGuard(count_and_allow)

    # block listed first: counter (later in the list) never runs
    Agent = rt.agent_node(
        name="block-first",
        llm=mock_llm(),
        model_middleware=[block, counter],
    )
    with rt.Session():
        with pytest.raises(GuardrailBlockedError):
            await rt.call(Agent, user_input="hi")
    assert counts["n"] == 0

    # counter listed first: it runs before the later guard blocks
    Agent2 = rt.agent_node(
        name="block-second",
        llm=mock_llm(),
        model_middleware=[counter, block],
    )
    with rt.Session():
        with pytest.raises(GuardrailBlockedError):
            await rt.call(Agent2, user_input="hi")
    assert counts["n"] == 1


# ---------------------------------------------------------------------------
# OUTPUT guards: list order == REVERSE evaluation order (each processes on the way back
# out, so the last-listed guard is closest to the model and fires first). Non-obvious —
# worth pinning down explicitly.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_output_guards_fire_in_reverse_list_order(mock_llm):
    trace = []

    guard_a = FnOutputGuard(lambda _e: (trace.append("A"), GuardrailDecision.allow())[1])
    guard_b = FnOutputGuard(lambda _e: (trace.append("B"), GuardrailDecision.allow())[1])

    Agent = rt.agent_node(
        name="order-output",
        llm=mock_llm(custom_response="ok"),
        model_middleware=[guard_a, guard_b],
    )
    with rt.Session():
        await rt.call(Agent, user_input="hi")

    # guard_b is closest to the raw model call (innermost), so it observes the
    # response and fires before guard_a, which wraps around it.
    assert trace == ["B", "A"]


# ---------------------------------------------------------------------------
# Guards are ordinary model_middleware: a plain (non-guard) middleware interleaved with
# a guard shows position — not "is it a guard" — decides order.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guard_and_plain_middleware_interleave_by_position(mock_llm):
    trace = []

    @before_llm
    async def plain_tracer(message_history, schema, tools):
        trace.append("plain")
        return message_history, schema, tools

    guard = FnInputGuard(lambda _e: (trace.append("guard"), GuardrailDecision.allow())[1])

    Agent = rt.agent_node(
        name="interleave-plain-first",
        llm=mock_llm(custom_response="ok"),
        model_middleware=[plain_tracer, guard],
    )
    with rt.Session():
        await rt.call(Agent, user_input="hi")
    assert trace == ["plain", "guard"]

    trace.clear()
    Agent2 = rt.agent_node(
        name="interleave-guard-first",
        llm=mock_llm(custom_response="ok"),
        model_middleware=[guard, plain_tracer],
    )
    with rt.Session():
        await rt.call(Agent2, user_input="hi")
    assert trace == ["guard", "plain"]
