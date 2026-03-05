from pydantic import BaseModel, Field
from datetime import datetime
from typing import TypeVar, Generic
from uuid import UUID, uuid4

from .metric_results import MetricResult, ToolMetricResult, LLMMetricResult
from .aggregate_results import AggregateForest, AggregateTreeNode
from ..evaluators.metrics import Metric, Numerical, Categorical, METRIC_TYPES

TMetric = TypeVar("TMetric", bound=Metric | Numerical | Categorical)
TMetricResult = TypeVar("TMetricResult", bound=MetricResult)
TAggregateResult = TypeVar("TAggregateResult", bound=  AggregateTreeNode)
class EvaluatorResult(BaseModel, Generic[TMetric, TMetricResult, TAggregateResult]):
    evaluator_name: str
    evaluator_id: str
    agent_data_ids: set[UUID] = Field(default_factory=set, exclude=True)
    metrics: list[TMetric] = Field(default_factory=list, exclude=True)
    # metric_results: list[TMetricResult] = Field(default_factory=list, exclude=True)
    metric_results: list[TMetricResult] = Field(default_factory=list)
    aggregate_results: list[TAggregateResult] | AggregateForest


class EvaluationResult(BaseModel):
    evaluation_id: UUID = Field(default_factory=uuid4)
    created_at: datetime
    completed_at: datetime
    evaluation_name: str | None = None
    agents: list[dict[str, str | list[dict[str, UUID]]]]
    metrics_map: dict[str, METRIC_TYPES]
    evaluator_results: list[EvaluatorResult]