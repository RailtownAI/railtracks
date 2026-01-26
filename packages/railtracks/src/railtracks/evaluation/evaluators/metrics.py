import hashlib
import json
from pydantic import BaseModel, ConfigDict, model_validator, field_serializer

class Metric(BaseModel):
    name: str
    identifier: str = ""
    model_config = ConfigDict(frozen=True)

    @model_validator(mode='before')
    @classmethod
    def _generate_identifier(cls, values):
        """Generate deterministic identifier from configuration."""
        config = {k: v for k, v in values.items() if k != 'identifier'}
        config['_type'] = cls.__name__
        
        for key, value in list(config.items()):
            if isinstance(value, type):
                config[key] = value.__name__
        
        config_str = json.dumps(config, sort_keys=True)
        identifier = hashlib.sha256(config_str.encode()).hexdigest()
        
        values['identifier'] = identifier
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
        fields = {k: v for k, v in self.model_dump().items() if k != 'identifier'}
        fields_str = ', '.join(f"{k}={repr(v)}" for k, v in fields.items())
        return f"{self.__class__.__name__}({fields_str})"

class Categorical(Metric):
    categories: list[str]

class Numerical(Metric):
    data_type: type[int | float] = float
    min_value: int | float | None = None
    max_value: int | float | None = None

    @model_validator(mode='before')
    def validate_min_max(cls, values):
        min_value = values.get('min_value')
        max_value = values.get('max_value')
        if min_value is not None and max_value is not None:
            if min_value >= max_value:
                raise ValueError("min_value must be less than max_value")
        return values
    
    @model_validator(mode='before')
    def validate_data_type(cls, values):
        data_type = values.get('data_type', float)
        if data_type not in (int, float):
            raise ValueError("data_type must be int or float")
        
        min_value = values.get('min_value')
        max_value = values.get('max_value')
        
        if min_value is not None and not isinstance(min_value, data_type):
            raise ValueError(
                f"min_value must be of type {data_type.__name__}, "
                f"got {type(min_value).__name__}"
            )
        if max_value is not None and not isinstance(max_value, data_type):
            raise ValueError(
                f"max_value must be of type {data_type.__name__}, "
                f"got {type(max_value).__name__}"
            )
        
        return values
    
    @field_serializer('data_type')
    def serialize_data_type(self, value: type) -> str:
        """Serialize type to string name for JSON."""
        return value.__name__