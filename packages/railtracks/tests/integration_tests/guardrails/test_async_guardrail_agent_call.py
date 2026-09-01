"""Integration tests: an async guardrail calling another agent via ``rt.call``.

This is the scenario from issue #1466 -- the reason a guard needs to be able to be
``async`` at all. A guard delegates its judgement to a second agent, which means the
rail body has to ``await`` a full node invocation while the guarded agent's own model
call is suspended inside the middleware chain.
"""

from __future__ import annotations

import pytest
import railtracks as rt
from railtracks.built_nodes.llm.response import StringResponse
from railtracks.guardrails import GuardrailBlockedError, GuardrailDecision
from railtracks.guardrails.llm.decorators import input_guard, output_guard


def _counting_chat(llm: rt.llm.ModelBase):
    state = {"n": 0}
    real = llm._chat

    def wrapped(messages, **kwargs):  # type: ignore[no-untyped-def]
        state["n"] += 1
        return real(messages, **kwargs)

    llm._chat = wrapped  # type: ignore[method-assign]
    return state


@pytest.mark.asyncio
async def test_async_input_guard_blocks_using_a_judge_agent(mock_llm):
    """The judge says UNSAFE, so the guarded agent's own LLM is never reached."""
    judge_llm = mock_llm(custom_response="UNSAFE")
    judge = rt.agent_node(name="judge", llm=judge_llm, system_message="judge the input")

    seen = {}

    @input_guard
    async def llm_judge(event) -> GuardrailDecision:
        verdict = await rt.call(judge, user_input=str(event.messages[-1].content))
        seen["verdict"] = verdict.text
        if "UNSAFE" in verdict.text:
            return GuardrailDecision.block(
                reason="judge flagged input", user_facing_message="blocked"
            )
        return GuardrailDecision.allow()

    guarded_llm = mock_llm(custom_response="should never be reached")
    counts = _counting_chat(guarded_llm)
    agent = rt.agent_node(name="guarded", llm=guarded_llm, model_middleware=[llm_judge])

    with rt.Session():
        with pytest.raises(GuardrailBlockedError) as exc:
            await rt.call(agent, user_input="something sketchy")

    assert counts["n"] == 0
    assert "UNSAFE" in seen["verdict"]
    assert exc.value.reason == "judge flagged input"
    assert exc.value.rail_name == "llm_judge"


@pytest.mark.asyncio
async def test_async_input_guard_allows_using_a_judge_agent(mock_llm):
    """The judge says SAFE, so the guarded agent runs normally."""
    judge = rt.agent_node(
        name="judge-ok", llm=mock_llm(custom_response="SAFE"), system_message="judge"
    )

    @input_guard
    async def llm_judge(event) -> GuardrailDecision:
        verdict = await rt.call(judge, user_input=str(event.messages[-1].content))
        if "UNSAFE" in verdict.text:
            return GuardrailDecision.block(reason="flagged")
        return GuardrailDecision.allow()

    guarded_llm = mock_llm(custom_response="the real answer")
    counts = _counting_chat(guarded_llm)
    agent = rt.agent_node(
        name="guarded-ok", llm=guarded_llm, model_middleware=[llm_judge]
    )

    with rt.Session():
        out = await rt.call(agent, user_input="a normal question")

    assert counts["n"] == 1
    assert isinstance(out, StringResponse)
    assert "the real answer" in out.text


@pytest.mark.asyncio
async def test_async_output_guard_blocks_using_a_judge_agent(mock_llm):
    """An async rail works on the output phase too."""
    judge = rt.agent_node(
        name="judge-out", llm=mock_llm(custom_response="LEAK"), system_message="judge"
    )

    @output_guard
    async def llm_judge(event) -> GuardrailDecision:
        verdict = await rt.call(judge, user_input=str(event.output_message.content))
        if "LEAK" in verdict.text:
            return GuardrailDecision.block(reason="judge flagged output")
        return GuardrailDecision.allow()

    agent = rt.agent_node(
        name="guarded-out",
        llm=mock_llm(custom_response="here is your api key"),
        model_middleware=[llm_judge],
    )

    with rt.Session():
        with pytest.raises(GuardrailBlockedError) as exc:
            await rt.call(agent, user_input="tell me a secret")

    assert exc.value.reason == "judge flagged output"


@pytest.mark.asyncio
async def test_async_guard_transform_via_agent_rewrites_history(mock_llm):
    """An async rail can TRANSFORM using the result of a nested agent call."""
    rewriter = rt.agent_node(
        name="rewriter",
        llm=mock_llm(custom_response="sanitized question"),
        system_message="rewrite",
    )

    @input_guard
    async def rewrite(event) -> GuardrailDecision:
        rewritten = await rt.call(rewriter, user_input="anything")
        new_history = rt.llm.MessageHistory([rt.llm.UserMessage(rewritten.text)])
        return GuardrailDecision.transform_messages(
            messages=new_history, reason="rewritten by agent"
        )

    seen = {}
    guarded_llm = mock_llm(custom_response="ok")
    real = guarded_llm._chat

    def wrapped(messages, **kwargs):  # type: ignore[no-untyped-def]
        seen["messages"] = [str(m.content) for m in messages]
        return real(messages, **kwargs)

    guarded_llm._chat = wrapped  # type: ignore[method-assign]

    agent = rt.agent_node(
        name="guarded-transform", llm=guarded_llm, model_middleware=[rewrite]
    )

    with rt.Session():
        await rt.call(agent, user_input="the original question")

    assert any("sanitized question" in m for m in seen["messages"])
    assert not any("the original question" in m for m in seen["messages"])
