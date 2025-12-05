from pydantic import BaseModel, Field, field_serializer
from uuid import UUID, uuid4
from typing import Any
from railtracks.llm import MessageHistory

class DataPoint(BaseModel):
    """A class representing a single data point"""
    agent_input: str | list[dict]
    expected_output: str | BaseModel | None = None
    identifier: UUID = Field(default_factory=uuid4)
    
    @field_serializer('agent_input', 'expected_output', when_used='json')
    def serialize_output(self, value: str | BaseModel | None) -> Any:
        """Serialize BaseModel instances to dicts for JSON."""
        if isinstance(value, BaseModel):
            return value.model_dump(mode='json')
        return value

class AgentDataPoint(BaseModel):
    """A data point specific to agent interactions."""
    agent_name: str
    agent_input: dict[str, Any]
    agent_output: str | BaseModel | None = None
    agent_internals: dict[str, str | dict | list] | None = None

    @field_serializer('agent_input', 'agent_output', when_used='json')
    def serialize_output(self, value: str | BaseModel | None) -> Any:
        """Serialize BaseModel instances to dicts for JSON."""
        if isinstance(value, BaseModel):
            return value.model_dump(mode='json')
        return value
    
