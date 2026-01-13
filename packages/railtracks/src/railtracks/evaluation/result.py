from collections import Counter
from datetime import datetime
from typing import Sequence
from uuid import UUID

from pydantic import BaseModel, Field

from .evaluators.metrics import Categorical, Metric, Numerical


class AgentRun(BaseModel):
    session_id: UUID
    run_id: UUID


class MetricResult(BaseModel):
    metric_name: str
    metric_id: UUID
    value: str | float | int


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


class AggregateNumericalResult(Metric):
    metric: Numerical
    values: list[float | int]
    average: float | None = None
    minimum: int | float | None = None
    maximum: int | float | None = None
    median: int | float | None = None
    std: float | None = None
    mode: int | float | None = None

    def model_post_init(self, __context) -> None:
        """Aggregate numerical values from the provided metrics."""
        if not self.values:
            return

        self.average = sum(self.values) / len(self.values)
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

        variance = sum((x - self.average) ** 2 for x in self.values) / len(self.values)
        self.std = variance**0.5

        value_counts = Counter(self.values)
        if value_counts:
            self.mode = value_counts.most_common(1)[0][0]


class EvaluatorResult(BaseModel):
    evaluator_name: str
    agent_name: str
    evaluator_id: UUID
    metrics: list[Metric]
    results: Sequence[
        tuple[UUID, MetricResult]
        | AggregateCategoricalResult
        | AggregateNumericalResult
        | MetricResult
    ]


class EvaluationResult(BaseModel):
    evaluation_id: UUID
    evaluation_name: str
    agent_name: str
    created_at: datetime
    agent_run_ids: list[UUID] = Field(
        default_factory=list,
        description="If applicable, list of agent run UUIDs that were part of this evaluation",
    )
    data_points: list[UUID] = Field(
        default_factory=list,
        description="If applicable, list of data point UUIDs that were evaluated",
    )
    results: list[EvaluatorResult]
    metrics: list[Metric]
