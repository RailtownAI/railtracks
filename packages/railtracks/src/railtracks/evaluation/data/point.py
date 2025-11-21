from pydantic import BaseModel, Field
from uuid import UUID, uuid4

class DataPoint(BaseModel):
    """A class representing a single data point"""
    agent_input: str
    agent_output: str | BaseModel
    expected_output: str | BaseModel | None = None
    _id: UUID = Field(default_factory=uuid4)