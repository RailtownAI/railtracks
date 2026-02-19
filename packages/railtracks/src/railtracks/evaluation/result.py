from collections import Counter
from datetime import datetime, timezone
from typing import TypeVar, Generic
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_serializer

from .evaluators.metrics import Categorical, Metric, Numerical, METRIC_TYPES

class MetricResult(BaseModel):
    type: str = "Base"
    result_name: str  # primary for human readability and debugging
    metric_id: str
    agent_data_id: list[UUID]
    value: str | float | int


class ToolMetricResult(MetricResult):
    type: str = "Tool"
    value: float | int  # type: ignore[assignment] pydantic supports narrowing types in subclasses
    tool_name: str
    tool_node_id: UUID | None = None


class LLMMetricResult(MetricResult):
    type: str = "LLM"
    llm_call_index: int
    model_name: str
    model_provider: str


class AggregateCategoricalResult(BaseModel):
    type: str = "AggregateCategorical"
    metric: Categorical
    labels: list[str]
    most_common_label: str | None = None
    least_common_label: str | None = None
    counts: dict[str, int] = Field(default_factory=dict)

    def model_post_init(self, __context) -> None:
        """Aggregate categories from the provided metrics."""

        for label in self.labels:
            if label not in self.metric.categories:
                raise Exception("Unknown label")

        counts = Counter(self.labels)
        self.counts = dict(counts)
        if counts:
            self.most_common_label = counts.most_common(1)[0][0]
            self.least_common_label = counts.most_common()[-1][0]


class AggregateNumericalResult(BaseModel):
    type: str = "AggregateNumerical"
    metric: Numerical
    values: list[float | int]
    mean: float | None = None
    minimum: float | int | None = None
    maximum: float | int | None = None
    median: float | int | None = None
    std: float | None = None
    mode: float | int | None = None

    def model_post_init(self, __context) -> None:
        """Aggregate numerical values from the provided metrics."""
        if not self.values:
            return

        self.mean = sum(self.values) / len(self.values)
        self.minimum = min(self.values)
        self.maximum = max(self.values)

        # The following typically would use numpy but since it's not a dependency yet
        # might as well implement manually
        sorted_values = sorted(self.values)
        n = len(sorted_values)
        if n % 2 == 0:
            self.median = (sorted_values[n // 2 - 1] + sorted_values[n // 2]) / 2
        else:
            self.median = sorted_values[n // 2]

        variance = sum((x - self.mean) ** 2 for x in self.values) / len(self.values)
        self.std = variance**0.5

        value_counts = Counter(self.values)
        if value_counts:
            self.mode = value_counts.most_common(1)[0][0]


class ToolAggregateResult(AggregateNumericalResult):
    type: str = "ToolAggregate"
    tool_name: str
    tool_node_ids: dict[UUID, list[UUID]] | None = None

class LLMInferenceAggregateResult(AggregateNumericalResult):
    type: str = "LLMInferenceAggregate"
    llm_call_index: int
    model_name: str
    model_provider: str

TMetric = TypeVar("TMetric", bound=Metric | Numerical | Categorical)
TMetricResult = TypeVar("TMetricResult", bound=MetricResult)
TAggregateResult = TypeVar("TAggregateResult", bound=AggregateCategoricalResult | AggregateNumericalResult)
class EvaluatorResult(BaseModel, Generic[TMetric, TMetricResult, TAggregateResult]):
    evaluator_name: str
    evaluator_id: str
    agent_data_ids: set[UUID] = Field(default_factory=set)
    metrics: list[TMetric]
    metric_results: list[TMetricResult]
    aggregate_results: list[TAggregateResult]

    @model_serializer(mode='wrap', when_used='json')
    def _serialize_model(self, serializer, info):
        """Exclude metrics and agent_data_ids from JSON serialization."""
        data = serializer(self)
        data.pop('metrics', None)
        data.pop('agent_data_ids', None)
        return data


class EvaluationResult(BaseModel):
    evaluation_id: UUID = Field(default_factory=uuid4)
    created_at: datetime
    completed_at: datetime
    evaluation_name: str | None = None
    agent_name: str
    agents: list[dict[str, list[UUID]]]
    metrics_map: dict[str, METRIC_TYPES]
    evaluator_results: list[EvaluatorResult]
