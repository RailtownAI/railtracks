from pydantic import BaseModel, field_serializer
from typing import Any

class AgentDataPoint(BaseModel):
    """A data point specific to agent interactions."""
    agent_name: str
    agent_input: dict[str, Any]
    agent_output: Any = None
    agent_internals: dict[str, Any] | None = None

    @field_serializer('agent_output', when_used='json')
    def serialize_output(self, value: Any) -> Any:
        """Serialize BaseModel instances to dicts for JSON."""
        if isinstance(value, BaseModel):
            return value.model_dump(mode='json')
        return value