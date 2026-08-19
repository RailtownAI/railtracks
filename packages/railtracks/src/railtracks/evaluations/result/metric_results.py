from typing import Generic, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

TMetricValue = TypeVar("TMetricValue")


class MetricResult(BaseModel, Generic[TMetricValue]):
    identifier: UUID = Field(default_factory=uuid4)
    type: str = "Base"
    result_name: str  # primary for human readability and debugging
    metric_id: str
    agent_data_id: list[UUID]
    value: TMetricValue


class ToolMetricResult(MetricResult[float | int]):
    type: str = "Tool"
    tool_name: str
    tool_node_id: UUID | None = None


class LLMMetricResult(MetricResult[float | int | None]):
    type: str = "LLM"
    llm_call_index: int
    model_name: str
    model_provider: str
