"""End-to-end: real session → workspace SQLite → AgentDataPoint → evaluator.

This is the full loop the evaluations port (Step 8) must support: run a
tool-calling agent, then evaluate it straight from the workspace DB by
session id — no JSON files anywhere.
"""

from __future__ import annotations

import pytest
import railtracks as rt
from railtracks.evaluations.evaluators.llm_inference_evaluator import (
    LLMInferenceEvaluator,
)
from railtracks.evaluations.point import extract_agent_data_points
from railtracks.llm import ToolCall


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("RAILTRACKS_ALLOW_PERSISTENCE", "1")
    monkeypatch.setenv("RAILTRACKS_HOME", str(tmp_path))
    return tmp_path / ".railtracks"


async def test_extract_and_evaluate_from_real_session(isolated_home, mock_llm) -> None:
    def secret_phrase():
        return "Constantinople"

    llm = mock_llm(
        requested_tool_calls=[
            ToolCall(name="secret_phrase", identifier="id_42424242", arguments={})
        ],
    )
    agent = rt.agent_node(
        tool_nodes={rt.function_node(secret_phrase)},
        name="SecretPhraseAgent",
        system_message="Answer using your tools.",
        llm=llm,
    )

    with rt.Session(flow_name="eval-e2e") as sess:
        await rt.call(agent, user_input="What is the secret phrase?")

    data_points = extract_agent_data_points(
        sess._identifier, railtracks_home=isolated_home
    )

    assert len(data_points) == 1
    dp = data_points[0]
    assert dp.agent_name == "SecretPhraseAgent"
    assert str(dp.session_id) == sess._identifier

    # llm metrics came from the MockLLM message info
    assert len(dp.llm_details.calls) >= 1
    call = dp.llm_details.calls[0]
    assert call.model_name == "MockLLM"
    assert call.input_tokens == 42
    assert call.total_cost == 0.00042

    # the tool invocation surfaced as a tool detail
    assert "secret_phrase" in dp.tool_details.tool_names
    tool_call = dp.tool_details.calls[0]
    assert tool_call.output == "Constantinople"
    assert tool_call.status.value == "Completed"

    # and a real evaluator runs on it end-to-end
    result = LLMInferenceEvaluator().run(data_points)
    assert result.agent_data_ids == {dp.identifier}
    input_tokens = [
        r for r in result.metric_results if r.result_name == "InputTokens"
    ]
    assert input_tokens and all(r.value == 42 for r in input_tokens)


async def test_extract_all_sessions_from_workspace(isolated_home, mock_llm) -> None:
    agent = rt.agent_node(
        name="PlainAgent",
        system_message="Just answer.",
        llm=mock_llm(custom_response="hello"),
    )
    with rt.Session(flow_name="first"):
        await rt.call(agent, user_input="hi")
    with rt.Session(flow_name="second"):
        await rt.call(agent, user_input="hi again")

    data_points = extract_agent_data_points(railtracks_home=isolated_home)
    assert len(data_points) == 2
    assert {dp.agent_name for dp in data_points} == {"PlainAgent"}
