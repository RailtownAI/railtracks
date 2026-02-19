from pydantic import BaseModel
from uuid import UUID

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