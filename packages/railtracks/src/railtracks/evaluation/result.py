from collections import Counter
from datetime import datetime, timezone
from typing import TypeVar, Generic
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .evaluators.metrics import Categorical, Metric, Numerical


class MetricResult(BaseModel):
    result_name: str  # primary for human readability and debugging
    metric_id: str
    agent_data_id: list[UUID]
    value: str | float | int


class ToolMetricResult(MetricResult):
    value: float | int  # type: ignore[assignment] pydantic supports narrowing types in subclasses
    tool_name: str
    tool_call_id: str | None = None


class LLMMetricResult(MetricResult):
    llm_call_index: int
    model_name: str
    model_provider: str


class AggregateCategoricalResult(BaseModel):
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
    tool_name: str

class LLMInferenceAggregateResult(AggregateNumericalResult):
    llm_call_index: int
    model_name: str
    model_provider: str

TMetric = TypeVar("TMetric", bound=Metric)
TMetricResult = TypeVar("TMetricResult", bound=MetricResult | AggregateCategoricalResult | AggregateNumericalResult)
class EvaluatorResult(BaseModel, Generic[TMetric, TMetricResult]):
    evaluator_name: str
    evaluator_id: str
    agent_data_ids: set[UUID] = Field(default_factory=set)
    metrics: list[TMetric]
    results: list[TMetricResult]


class EvaluationResult(BaseModel):
    evaluation_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    evaluation_name: str | None = None
    agent_name: str
    agent_data_ids: list[UUID] = Field(
        default_factory=list,
        description="If applicable, list of agent run UUIDs that were part of this evaluation",
    )
    results: list[EvaluatorResult]
    metrics: list[Metric | Numerical | Categorical]
