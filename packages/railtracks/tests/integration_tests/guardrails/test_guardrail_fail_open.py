"""End-to-end tests for Guard.fail_open through a real agent_node call. Unit-level
fail_open behavior is covered by test_base_llm_guardrail_run.py; these confirm the
same guarantee holds once the guard is wired into model_middleware and actually
invoked through the LLM call path (context injection, ModelInvoker, llm_invoke_factory
error handling all sit between the guard and the caller).
"""

from __future__ import annotations

import pytest
import railtracks as rt
from railtracks.built_nodes.llm.response import StringResponse
from railtracks.guardrails.core import (
    GuardrailBlockedError,
    GuardrailDecision,
    InputGuard,
    LLMGuardrailEvent,
    OutputGuard,
)


class RaisingInputGuard(InputGuard):
    def __call__(self, event: LLMGuardrailEvent) -> GuardrailDecision:
        raise RuntimeError("unexpected guard failure")


class RaisingOutputGuard(OutputGuard):
    def __call__(self, event: LLMGuardrailEvent) -> GuardrailDecision:
        raise RuntimeError("unexpected guard failure")


@pytest.mark.asyncio
async def test_input_guard_exception_blocks_the_call_by_default(mock_llm):
    Agent = rt.agent_node(
        name="fail-closed-input",
        llm=mock_llm(custom_response="ok"),
        model_middleware=[RaisingInputGuard(fail_open=False)],
    )
    with rt.Session():
        with pytest.raises(GuardrailBlockedError):
            await rt.call(Agent, user_input="hi")


@pytest.mark.asyncio
async def test_input_guard_exception_does_not_block_the_call_when_fail_open(mock_llm):
    Agent = rt.agent_node(
        name="fail-open-input",
        llm=mock_llm(custom_response="ok"),
        model_middleware=[RaisingInputGuard(fail_open=True)],
    )
    with rt.Session():
        result = await rt.call(Agent, user_input="hi")

    assert isinstance(result, StringResponse)
    assert "ok" in result.text


@pytest.mark.asyncio
async def test_output_guard_exception_blocks_the_call_by_default(mock_llm):
    Agent = rt.agent_node(
        name="fail-closed-output",
        llm=mock_llm(custom_response="ok"),
        model_middleware=[RaisingOutputGuard(fail_open=False)],
    )
    with rt.Session():
        with pytest.raises(GuardrailBlockedError):
            await rt.call(Agent, user_input="hi")


@pytest.mark.asyncio
async def test_output_guard_exception_does_not_block_the_call_when_fail_open(mock_llm):
    Agent = rt.agent_node(
        name="fail-open-output",
        llm=mock_llm(custom_response="ok"),
        model_middleware=[RaisingOutputGuard(fail_open=True)],
    )
    with rt.Session():
        result = await rt.call(Agent, user_input="hi")

    assert isinstance(result, StringResponse)
    assert "ok" in result.text
