import pytest

from railtracks.evaluations.evaluators.metrics import (
    Categorical,
    Category,
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


def test_categorical_accepts_category_objects():
    c = Categorical(
        name="quality",
        categories=[
            Category(name="good", label="pass"),
            Category(name="bad", label="fail"),
        ],
    )
    assert c.categories == [Category(name="good", label="pass"), Category(name="bad", label="fail")]
    assert c.categories[0].label == "pass"
    assert c.categories[1].label == "fail"


def test_categorical_accepts_mixed_strings_and_categories():
    c = Categorical(
        name="quality",
        categories=["good", Category(name="bad", label="fail")],
    )
    assert c.categories == ["good", "bad"]
    assert c.categories[0].label is None
    assert c.categories[1].label == "fail"


def test_categorical_string_and_category_inputs_produce_equivalent_categories():
    from_strings = Categorical(name="quality", categories=["good", "bad"])
    from_categories = Categorical(
        name="quality",
        categories=[Category(name="good"), Category(name="bad")],
    )
    assert from_strings.categories == from_categories.categories


def test_categorical_identifier_generation_does_not_crash_with_category_objects():
    """Regression test: constructing with raw Category objects used to fail during
    identifier hashing because Category isn't JSON-serializable by default."""
    c = Categorical(name="quality", categories=[Category(name="good", label="pass")])
    assert isinstance(c.identifier, str)
    assert len(c.identifier) == 64


def test_categorical_category_names_with_string_input():
    c = Categorical(name="quality", categories=["good", "bad", "ugly"])
    assert c.category_names == ["good", "bad", "ugly"]


def test_categorical_category_names_with_category_object_input():
    c = Categorical(
        name="quality",
        categories=[Category(name="good", label="pass"), Category(name="bad", label="fail")],
    )
    assert c.category_names == ["good", "bad"]


# ── Category ──────────────────────────────────────────────────────────────────


def test_category_equals_matching_string():
    assert Category(name="good") == "good"
    assert "good" == Category(name="good")


def test_category_not_equal_mismatched_string():
    assert Category(name="good") != "bad"


def test_category_equality_ignores_label():
    assert Category(name="good", label="pass") == Category(name="good", label="fail")


def test_category_hash_matches_name_hash():
    assert hash(Category(name="good")) == hash("good")


def test_category_usable_as_dict_key_via_string():
    counts = {Category(name="good"): 0}
    counts["good"] += 1
    assert counts[Category(name="good")] == 1


def test_category_str_returns_name():
    assert str(Category(name="good", label="pass")) == "good"


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
