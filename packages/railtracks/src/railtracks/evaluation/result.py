from collections import Counter
from datetime import datetime
from typing import Sequence
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

from .evaluators.metrics import Categorical, Metric, Numerical


class MetricResult(BaseModel):
    metric_name: str  # primary for human readability and debugging
    metric_id: str
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


class AggregateNumericalResult(BaseModel):
    metric: Numerical
    values: list[float | int]
    mean: float | None = None
    minimum: int | float | None = None
    maximum: int | float | None = None
    median: int | float | None = None
    std: float | None = None
    mode: int | float | None = None

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


class EvaluatorResult(BaseModel):
    evaluator_name: str
    evaluator_id: UUID
    # agent_data_ids: set[UUID]
    metrics: list[Metric]
    results: Sequence[
        tuple[UUID, MetricResult]
        | MetricResult
        | AggregateCategoricalResult
        | AggregateNumericalResult
    ]

    # @model_validator(mode="before")
    # @classmethod
    # def validate_results(cls, values):
    #     """Validate that UUIDs in tuple results are present in agent_data_ids."""
    #     results = values.get("results", [])
    #     agent_data_ids = values.get("agent_data_ids", [])

    #     for result in results:
    #         # only need to check if result is a tuple (UUID, MetricResult)
    #         if isinstance(result, tuple) and len(result) >= 2:
    #             uuid_value = result[0]

    #             if uuid_value not in agent_data_ids:
    #                 raise ValueError(
    #                     f"Result UUID {uuid_value} not found in agent_data_ids"
    #                 )


class EvaluationResult(BaseModel):
    evaluation_id: UUID = Field(default_factory=uuid4)
    evaluation_name: str | None = None
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
