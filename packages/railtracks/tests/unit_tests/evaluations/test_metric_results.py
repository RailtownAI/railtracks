from uuid import UUID, uuid4

import pytest
from railtracks.evaluations.result.metric_results import (
    LLMMetricResult,
    MetricResult,
    ToolMetricResult,
)

# ── MetricResult ──────────────────────────────────────────────────────────────


def test_metric_result_has_uuid_identifier():
    r = MetricResult(result_name="test", metric_id="abc", agent_data_id=[uuid4()], value=1.0)
    assert isinstance(r.identifier, UUID)


def test_metric_result_default_type():
    r = MetricResult(result_name="test", metric_id="abc", agent_data_id=[uuid4()], value=0)
    assert r.type == "Base"


def test_metric_result_float_value():
    adp = uuid4()
    r = MetricResult(result_name="latency", metric_id="m", agent_data_id=[adp], value=3.14)
    assert r.value == pytest.approx(3.14)


def test_metric_result_int_value():
    r = MetricResult(result_name="count", metric_id="m", agent_data_id=[uuid4()], value=42)
    assert r.value == 42


def test_metric_result_string_value():
    r = MetricResult(result_name="label", metric_id="m", agent_data_id=[uuid4()], value="good")
    assert r.value == "good"


def test_metric_result_multiple_agent_data_ids():
    ids = [uuid4(), uuid4()]
    r = MetricResult(result_name="r", metric_id="m", agent_data_id=ids, value=1)
    assert r.agent_data_id == ids


def test_metric_result_unique_identifiers():
    r1 = MetricResult(result_name="r", metric_id="m", agent_data_id=[uuid4()], value=1)
    r2 = MetricResult(result_name="r", metric_id="m", agent_data_id=[uuid4()], value=1)
    assert r1.identifier != r2.identifier


# ── ToolMetricResult ──────────────────────────────────────────────────────────


def test_tool_metric_result_type():
    r = ToolMetricResult(
        result_name="Runtime/tool_a",
        metric_id="m",
        agent_data_id=[uuid4()],
        value=0.5,
        tool_name="tool_a",
    )
    assert r.type == "Tool"


def test_tool_metric_result_tool_name():
    r = ToolMetricResult(
        result_name="r",
        metric_id="m",
        agent_data_id=[uuid4()],
        value=1,
        tool_name="my_tool",
    )
    assert r.tool_name == "my_tool"


def test_tool_metric_result_node_id_defaults_to_none():
    r = ToolMetricResult(
        result_name="r",
        metric_id="m",
        agent_data_id=[uuid4()],
        value=0,
        tool_name="t",
    )
    assert r.tool_node_id is None


def test_tool_metric_result_with_node_id():
    nid = uuid4()
    r = ToolMetricResult(
        result_name="r",
        metric_id="m",
        agent_data_id=[uuid4()],
        value=1,
        tool_name="t",
        tool_node_id=nid,
    )
    assert r.tool_node_id == nid


def test_tool_metric_result_value_is_numeric():
    r = ToolMetricResult(
        result_name="r",
        metric_id="m",
        agent_data_id=[uuid4()],
        value=2.5,
        tool_name="t",
    )
    assert isinstance(r.value, float)


# ── LLMMetricResult ───────────────────────────────────────────────────────────


def test_llm_metric_result_type():
    r = LLMMetricResult(
        result_name="cost",
        metric_id="m",
        agent_data_id=[uuid4()],
        value=0.001,
        llm_call_index=0,
        model_name="gpt-4",
        model_provider="OpenAI",
    )
    assert r.type == "LLM"


def test_llm_metric_result_fields():
    r = LLMMetricResult(
        result_name="tokens",
        metric_id="m",
        agent_data_id=[uuid4()],
        value=100,
        llm_call_index=2,
        model_name="claude-3",
        model_provider="Anthropic",
    )
    assert r.llm_call_index == 2
    assert r.model_name == "claude-3"
    assert r.model_provider == "Anthropic"


def test_llm_metric_result_inherits_identifier():
    r = LLMMetricResult(
        result_name="r",
        metric_id="m",
        agent_data_id=[uuid4()],
        value=1,
        llm_call_index=0,
        model_name="gpt-4",
        model_provider="OpenAI",
    )
    assert isinstance(r.identifier, UUID)
