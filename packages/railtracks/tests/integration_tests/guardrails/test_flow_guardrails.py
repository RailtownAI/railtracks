"""Smoke test: Flow entry point with a guarded terminal agent."""

from __future__ import annotations

import pytest
import railtracks as rt
from railtracks.orchestration.flow import Flow

from railtracks.guardrails import Guard, GuardrailDecision


@pytest.mark.asyncio
async def test_flow_ainvoke_guarded_terminal_smoke(mock_llm):
    def allow(_e) -> GuardrailDecision:  # type: ignore[no-untyped-def]
        return GuardrailDecision.allow()

    llm = mock_llm(custom_response="flow-ok")
    Agent = rt.agent_node(
        name="flow-guarded",
        llm=llm,
        guardrails=Guard(input=[allow]),
        system_message="You echo.",
    )
    flow = Flow(name="guard-flow", entry_point=Agent)

    result = await flow.ainvoke(user_input="ping")

    assert hasattr(result, "text")
    assert "flow-ok" in result.text


def test_flow_invoke_sync_guarded_terminal_smoke(mock_llm):
    def allow(_e) -> GuardrailDecision:  # type: ignore[no-untyped-def]
        return GuardrailDecision.allow()

    llm = mock_llm(custom_response="sync")
    Agent = rt.agent_node(
        name="flow-guarded-sync",
        llm=llm,
        guardrails=Guard(input=[allow]),
    )
    flow = Flow(name="guard-flow-sync", entry_point=Agent)

    result = flow.invoke(user_input="ping")

    assert "sync" in result.text
