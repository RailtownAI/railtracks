from datetime import datetime
from typing import Sequence
from uuid import UUID
from pydantic import BaseModel, Field
from collections import Counter
from .evaluators.metrics import Metric, Numerical, Categorical

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

class EvaluatorResult(BaseModel):
    evaluator_name: str
    agent_name: str
    evaluator_id: UUID
    metrics: list[Metric]
    results: Sequence[tuple[UUID, MetricResult] | AggregateCategoricalResult | MetricResult]
    
class EvaluationResult(BaseModel):    
    evaluation_id: UUID
    evaluation_name: str
    agent_name: str
    created_at: datetime
    agent_run_ids: list[UUID] = Field(default_factory=list, description="If applicable, list of agent run UUIDs that were part of this evaluation")
    data_points: list[UUID] = Field(default_factory=list, description="If applicable, list of data point UUIDs that were evaluated")
    results: list[EvaluatorResult]
    metrics: list[Metric]
