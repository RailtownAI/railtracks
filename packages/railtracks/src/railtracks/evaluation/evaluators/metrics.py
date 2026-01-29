import hashlib
import json
from typing import TypeVar, Generic
from pydantic import BaseModel, ConfigDict, model_validator, field_serializer


class Metric(BaseModel):
    name: str
    identifier: str = ""
    model_config = ConfigDict(frozen=True)

    @model_validator(mode="before")
    @classmethod
    def _generate_identifier(cls, values):
        """Generate deterministic identifier from configuration."""
        # Only generate identifier if not already provided
        if values.get("identifier", "") != "":
            return values
        
        config = {k: v for k, v in values.items() if k != "identifier"}
        config["_type"] = cls.__name__

        for key, value in list(config.items()):
            if isinstance(value, type):
                config[key] = value.__name__

        config_str = json.dumps(config, sort_keys=True)
        identifier = hashlib.sha256(config_str.encode()).hexdigest()

        values["identifier"] = identifier
        return values

    def __hash__(self):
        """Hash by identifier for set/dict key usage."""
        return hash(self.identifier)

    def __eq__(self, other):
        """Equality based on identifier."""
        if not isinstance(other, Metric):
            return False
        return self.identifier == other.identifier

    def __str__(self) -> str:
        """Custom string represention excluding the identifier field"""
        fields = {k: v for k, v in self.model_dump().items() if k != "identifier"}
        fields_str = ", ".join(f"{k}={repr(v)}" for k, v in fields.items())
        return f"{self.__class__.__name__}({fields_str})"


class Categorical(Metric):
    categories: list[str]


T = TypeVar("T", int, float)

class Numerical(Metric, Generic[T]):
    min_value: T | None = None
    max_value: T | None = None

    @model_validator(mode="before")
    @classmethod
    def validate_min_max(cls, values):
        min_value = values.get("min_value")
        max_value = values.get("max_value")
        if min_value is not None and max_value is not None:
            if min_value >= max_value:
                raise ValueError("min_value must be less than max_value")
        return values

class ToolMetric(Numerical):
    """A Numerical metric specific to tool usage statistics."""
    pass # TODO: needed?

class LLMMetric(Numerical):
    """A Numerical metric specific to tool usage statistics."""
    model_name: str
    model_provider: str