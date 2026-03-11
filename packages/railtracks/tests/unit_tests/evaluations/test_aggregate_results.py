from uuid import uuid4

import pytest
from railtracks.evaluations.evaluators.metrics import (
    Categorical,
    LLMMetric,
    Numerical,
    ToolMetric,
)
from railtracks.evaluations.result.aggregate_results import (
    AggregateForest,
    CategoricalAggregateNode,
    LLMInferenceAggregateNode,
    NumericalAggregateNode,
    ToolAggregateNode,
)
from railtracks.evaluations.result.metric_results import (
    LLMMetricResult,
    MetricResult,
    ToolMetricResult,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def make_forest():
    return AggregateForest[NumericalAggregateNode, MetricResult]()


def make_metric_result(value: float | int | str = 1.0) -> MetricResult:
    return MetricResult(
        result_name="r",
        metric_id="m",
        agent_data_id=[uuid4()],
        value=value,
    )


# ── AggregateForest ───────────────────────────────────────────────────────────


def test_forest_add_and_get_metric_result():
    forest = make_forest()
    mr = make_metric_result(2.0)
    forest.add_node(mr)
    assert forest.get(mr.identifier) is mr


def test_forest_get_missing_key_raises():
    forest = make_forest()
    with pytest.raises(KeyError):
        forest.get(uuid4())


def test_forest_add_multiple_nodes():
    forest = make_forest()
    mr1 = make_metric_result(1.0)
    mr2 = make_metric_result(2.0)
    forest.add_node(mr1)
    forest.add_node(mr2)
    assert forest.get(mr1.identifier) is mr1
    assert forest.get(mr2.identifier) is mr2


# ── NumericalAggregateNode – leaf children ────────────────────────────────────


@pytest.fixture
def numerical_metric():
    return Numerical(name="Latency")


def test_numerical_node_values_from_leaves(numerical_metric):
    forest = make_forest()
    mr1 = make_metric_result(2.0)
    mr2 = make_metric_result(4.0)
    forest.add_node(mr1)
    forest.add_node(mr2)

    node = NumericalAggregateNode(
        name="Agg",
        metric=numerical_metric,
        children=[mr1.identifier, mr2.identifier],
        forest=forest,
    )
    assert sorted(node.values) == [2.0, 4.0]


def test_numerical_node_mean(numerical_metric):
    forest = make_forest()
    mr1 = make_metric_result(2.0)
    mr2 = make_metric_result(4.0)
    forest.add_node(mr1)
    forest.add_node(mr2)

    node = NumericalAggregateNode(
        name="Agg", metric=numerical_metric,
        children=[mr1.identifier, mr2.identifier], forest=forest,
    )
    assert node.mean == pytest.approx(3.0)


def test_numerical_node_minimum_maximum(numerical_metric):
    forest = make_forest()
    mrs = [make_metric_result(v) for v in [1.0, 5.0, 3.0]]
    for mr in mrs:
        forest.add_node(mr)

    node = NumericalAggregateNode(
        name="Agg", metric=numerical_metric,
        children=[mr.identifier for mr in mrs], forest=forest,
    )
    assert node.minimum == pytest.approx(1.0)
    assert node.maximum == pytest.approx(5.0)


def test_numerical_node_median_odd(numerical_metric):
    forest = make_forest()
    mrs = [make_metric_result(v) for v in [1.0, 3.0, 5.0]]
    for mr in mrs:
        forest.add_node(mr)

    node = NumericalAggregateNode(
        name="Agg", metric=numerical_metric,
        children=[mr.identifier for mr in mrs], forest=forest,
    )
    assert node.median == pytest.approx(3.0)


def test_numerical_node_median_even(numerical_metric):
    forest = make_forest()
    mrs = [make_metric_result(v) for v in [1.0, 3.0, 5.0, 7.0]]
    for mr in mrs:
        forest.add_node(mr)

    node = NumericalAggregateNode(
        name="Agg", metric=numerical_metric,
        children=[mr.identifier for mr in mrs], forest=forest,
    )
    assert node.median == pytest.approx(4.0)


def test_numerical_node_std(numerical_metric):
    forest = make_forest()
    mr1 = make_metric_result(2.0)
    mr2 = make_metric_result(4.0)
    forest.add_node(mr1)
    forest.add_node(mr2)

    node = NumericalAggregateNode(
        name="Agg", metric=numerical_metric,
        children=[mr1.identifier, mr2.identifier], forest=forest,
    )
    assert node.std == pytest.approx(1.0)


def test_numerical_node_mode(numerical_metric):
    forest = make_forest()
    mrs = [make_metric_result(v) for v in [3, 3, 7]]
    for mr in mrs:
        forest.add_node(mr)

    node = NumericalAggregateNode(
        name="Agg", metric=numerical_metric,
        children=[mr.identifier for mr in mrs], forest=forest,
    )
    assert node.mode == 3


# ── NumericalAggregateNode – empty ────────────────────────────────────────────


def test_numerical_node_empty_returns_none(numerical_metric):
    forest = make_forest()
    node = NumericalAggregateNode(
        name="Empty", metric=numerical_metric, children=[], forest=forest,
    )
    assert node.values == []
    assert node.mean is None
    assert node.minimum is None
    assert node.maximum is None
    assert node.median is None
    assert node.std is None
    assert node.mode is None


# ── NumericalAggregateNode – is_leaf / is_parent ──────────────────────────────


def test_numerical_node_is_leaf(numerical_metric):
    forest = make_forest()
    leaf = NumericalAggregateNode(name="Leaf", metric=numerical_metric, children=[], forest=forest)
    assert leaf.is_leaf
    assert not leaf.is_parent


def test_numerical_node_is_parent(numerical_metric):
    forest = make_forest()
    mr = make_metric_result(1.0)
    forest.add_node(mr)
    parent = NumericalAggregateNode(
        name="Parent", metric=numerical_metric,
        children=[mr.identifier], forest=forest,
    )
    assert parent.is_parent
    assert not parent.is_leaf


# ── NumericalAggregateNode – recursive (nested nodes) ────────────────────────


def test_numerical_node_recursive_values(numerical_metric):
    forest = make_forest()
    mr = make_metric_result(5.0)
    forest.add_node(mr)

    child_node = NumericalAggregateNode(
        name="Child", metric=numerical_metric,
        children=[mr.identifier], forest=forest,
    )
    forest.add_node(child_node)

    parent_node = NumericalAggregateNode(
        name="Parent", metric=numerical_metric,
        children=[child_node.identifier], forest=forest,
    )
    assert parent_node.values == [5.0]
    assert parent_node.mean == pytest.approx(5.0)


def test_numerical_node_string_value_skipped(numerical_metric):
    """String MetricResult values should not contribute to numerical aggregates."""
    forest = make_forest()
    mr_valid = make_metric_result(3.0)
    mr_invalid = make_metric_result("label")  # string value
    forest.add_node(mr_valid)
    forest.add_node(mr_invalid)

    node = NumericalAggregateNode(
        name="Agg", metric=numerical_metric,
        children=[mr_valid.identifier, mr_invalid.identifier], forest=forest,
    )
    assert node.values == [3.0]


# ── CategoricalAggregateNode ──────────────────────────────────────────────────


@pytest.fixture
def categorical_metric():
    return Categorical(name="Quality", categories=["good", "bad", "neutral"])


@pytest.fixture
def categorical_forest():
    return AggregateForest[CategoricalAggregateNode, MetricResult]()


def test_categorical_node_categories(categorical_metric, categorical_forest):
    node = CategoricalAggregateNode(
        name="Agg", metric=categorical_metric, children=[], forest=categorical_forest,
    )
    assert node.categories == ["good", "bad", "neutral"]


def test_categorical_node_counts(categorical_metric, categorical_forest):
    mr1 = make_metric_result("good")
    mr2 = make_metric_result("good")
    mr3 = make_metric_result("bad")
    for mr in [mr1, mr2, mr3]:
        categorical_forest.add_node(mr)

    node = CategoricalAggregateNode(
        name="Agg", metric=categorical_metric,
        children=[mr1.identifier, mr2.identifier, mr3.identifier],
        forest=categorical_forest,
    )
    assert node.counts["good"] == 2
    assert node.counts["bad"] == 1
    assert node.counts["neutral"] == 0


def test_categorical_node_most_common_label(categorical_metric, categorical_forest):
    mr1 = make_metric_result("good")
    mr2 = make_metric_result("good")
    mr3 = make_metric_result("bad")
    for mr in [mr1, mr2, mr3]:
        categorical_forest.add_node(mr)

    node = CategoricalAggregateNode(
        name="Agg", metric=categorical_metric,
        children=[mr1.identifier, mr2.identifier, mr3.identifier],
        forest=categorical_forest,
    )
    assert node.most_common_label == "good"


def test_categorical_node_least_common_label():
    metric = Categorical(name="Quality", categories=["good", "bad"])
    forest = AggregateForest[CategoricalAggregateNode, MetricResult]()
    mr1 = make_metric_result("good")
    mr2 = make_metric_result("good")
    mr3 = make_metric_result("bad")
    for mr in [mr1, mr2, mr3]:
        forest.add_node(mr)

    node = CategoricalAggregateNode(
        name="Agg", metric=metric,
        children=[mr1.identifier, mr2.identifier, mr3.identifier],
        forest=forest,
    )
    assert node.least_common_label == "bad"


def test_categorical_node_invalid_label_raises(categorical_metric, categorical_forest):
    mr = make_metric_result("unknown")
    categorical_forest.add_node(mr)

    with pytest.raises(ValueError, match="Unknown label"):
        CategoricalAggregateNode(
            name="Agg", metric=categorical_metric,
            children=[mr.identifier], forest=categorical_forest,
        )


def test_categorical_node_empty_counts_all_zero(categorical_metric, categorical_forest):
    node = CategoricalAggregateNode(
        name="Agg", metric=categorical_metric, children=[], forest=categorical_forest,
    )
    assert all(v == 0 for v in node.counts.values())


# ── ToolAggregateNode ─────────────────────────────────────────────────────────


def test_tool_aggregate_node_type():
    metric = ToolMetric(name="Runtime", min_value=0.0)
    forest = AggregateForest[ToolAggregateNode, ToolMetricResult]()
    mr = ToolMetricResult(
        result_name="r", metric_id="m", agent_data_id=[uuid4()],
        value=0.5, tool_name="search",
    )
    forest.add_node(mr)

    node = ToolAggregateNode(
        name="SearchAgg", metric=metric, tool_name="search",
        children=[mr.identifier], forest=forest,
    )
    assert node.type == "ToolAggregate"
    assert node.tool_name == "search"
    assert node.mean == pytest.approx(0.5)


# ── LLMInferenceAggregateNode ─────────────────────────────────────────────────


def test_llm_inference_aggregate_node_type():
    metric = LLMMetric(name="TotalCost", min_value=0.0)
    forest = AggregateForest[LLMInferenceAggregateNode, LLMMetricResult]()
    mr = LLMMetricResult(
        result_name="r", metric_id="m", agent_data_id=[uuid4()],
        value=0.002, llm_call_index=0, model_name="gpt-4", model_provider="OpenAI",
    )
    forest.add_node(mr)

    node = LLMInferenceAggregateNode(
        name="CostAgg", metric=metric,
        children=[mr.identifier], forest=forest,
        llm_call_index=0, model_name="gpt-4", model_provider="OpenAI",
    )
    assert node.type == "LLMInferenceAggregate"
    assert node.llm_call_index == 0
    assert node.model_name == "gpt-4"
    assert node.model_provider == "OpenAI"
    assert node.mean == pytest.approx(0.002)
