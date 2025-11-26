from pydantic import BaseModel, Field, field_serializer
from uuid import UUID, uuid4
from typing import Any

class DataPoint(BaseModel):
    """A class representing a single data point"""
    agent_input: str
    agent_output: str | BaseModel
    expected_output: str | BaseModel | None = None
    identifier: UUID = Field(default_factory=uuid4)
    
    @field_serializer('agent_output', 'expected_output', when_used='json')
    def serialize_output(self, value: str | BaseModel | None) -> Any:
        """Serialize BaseModel instances to dicts for JSON."""
        if isinstance(value, BaseModel):
            return value.model_dump(mode='json')
        return value