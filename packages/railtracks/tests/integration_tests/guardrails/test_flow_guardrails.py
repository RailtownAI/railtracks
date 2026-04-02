"""Smoke test: Flow entry point with a guarded terminal agent."""

from __future__ import annotations

import pytest
import railtracks as rt
from railtracks.orchestration.flow import Flow

from railtracks.guardrails import Guard, GuardrailDecision, InputGuard, LLMGuardrailEvent


class FnInputGuard(InputGuard):
    """Wrap a plain callable as an InputGuard for testing."""

    def __init__(self, fn, name: str | None = None):
        super().__init__(name=name)
        self._fn = fn

    def __call__(self, event: LLMGuardrailEvent) -> GuardrailDecision:
        return self._fn(event)


@pytest.mark.asyncio
async def test_flow_ainvoke_guarded_terminal_smoke(mock_llm):
    llm = mock_llm(custom_response="flow-ok")
    Agent = rt.agent_node(
        name="flow-guarded",
        llm=llm,
        guardrails=Guard(input=[FnInputGuard(lambda _e: GuardrailDecision.allow())]),
        system_message="You echo.",
    )
    flow = Flow(name="guard-flow", entry_point=Agent)

    result = await flow.ainvoke(user_input="ping")

    assert hasattr(result, "text")
    assert "flow-ok" in result.text


def test_flow_invoke_sync_guarded_terminal_smoke(mock_llm):
    llm = mock_llm(custom_response="sync")
    Agent = rt.agent_node(
        name="flow-guarded-sync",
        llm=llm,
        guardrails=Guard(input=[FnInputGuard(lambda _e: GuardrailDecision.allow())]),
    )
    flow = Flow(name="guard-flow-sync", entry_point=Agent)

    result = flow.invoke(user_input="ping")

    assert "sync" in result.text
