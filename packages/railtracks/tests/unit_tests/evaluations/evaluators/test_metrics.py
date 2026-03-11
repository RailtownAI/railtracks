import pytest

from railtracks.evaluations.evaluators.metrics import (
    Categorical,
    LLMMetric,
    Metric,
    Numerical,
    ToolMetric,
)


# ── Metric ─────────────────────────────────────────────────────────────────────


def test_metric_identifier_is_deterministic():
    m1 = Metric(name="foo")
    m2 = Metric(name="foo")
    assert m1.identifier == m2.identifier


def test_metric_identifier_differs_by_name():
    m1 = Metric(name="foo")
    m2 = Metric(name="bar")
    assert m1.identifier != m2.identifier


def test_metric_hash_and_eq():
    m1 = Metric(name="foo")
    m2 = Metric(name="foo")
    assert m1 == m2
    assert hash(m1) == hash(m2)
    assert m1 != Metric(name="bar")


def test_metric_eq_non_metric_returns_false():
    m = Metric(name="foo")
    assert m != 42
    assert m != "foo"
    assert m != None  # noqa: E711


def test_metric_str_excludes_identifier():
    m = Metric(name="foo", description="desc")
    s = str(m)
    assert "identifier" not in s
    assert "foo" in s


def test_metric_explicit_identifier_preserved():
    m = Metric(name="foo", identifier="custom-id")
    assert m.identifier == "custom-id"


# ── Numerical ─────────────────────────────────────────────────────────────────


def test_numerical_valid_min_max():
    n = Numerical(name="score", min_value=0, max_value=100)
    assert n.min_value == 0
    assert n.max_value == 100


def test_numerical_min_greater_than_max_raises():
    with pytest.raises(Exception):
        Numerical(name="score", min_value=10, max_value=5)


def test_numerical_equal_min_max_raises():
    with pytest.raises(Exception):
        Numerical(name="score", min_value=5, max_value=5)


def test_numerical_no_bounds():
    n = Numerical(name="score")
    assert n.min_value is None
    assert n.max_value is None


# ── Categorical ───────────────────────────────────────────────────────────────


def test_categorical_stores_categories():
    c = Categorical(name="quality", categories=["good", "bad", "ugly"])
    assert c.categories == ["good", "bad", "ugly"]


def test_categorical_identifier_includes_categories():
    c1 = Categorical(name="q", categories=["a", "b"])
    c2 = Categorical(name="q", categories=["a", "c"])
    assert c1.identifier != c2.identifier


# ── LLMMetric / ToolMetric ────────────────────────────────────────────────────


def test_llm_metric_type():
    m = LLMMetric(name="Latency", min_value=0.0)
    assert m.metric_type == "LLMMetric"


def test_tool_metric_type():
    m = ToolMetric(name="Runtime", min_value=0.0)
    assert m.metric_type == "ToolMetric"


def test_llm_and_tool_same_config_differ_by_type():
    llm = LLMMetric(name="x", min_value=0.0)
    tool = ToolMetric(name="x", min_value=0.0)
    assert llm.identifier != tool.identifier
