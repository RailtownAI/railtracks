from pydantic import BaseModel, Field, field_serializer
from typing import Any
from uuid import UUID, uuid4

class AgentDataPoint(BaseModel):
    """A data point specific to agent interactions."""
    id: UUID = Field(default_factory=uuid4)
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