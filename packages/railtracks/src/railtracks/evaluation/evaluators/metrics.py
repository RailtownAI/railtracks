import hashlib
import json
from pydantic import BaseModel, Field
from uuid import UUID, uuid4

class Metric(BaseModel):
    name: str
    _id: UUID = Field(default_factory=uuid4)
    
    def _generate_config_hash(self) -> str:
        """Generate a deterministic hash based on metric configuration.
        
        Returns the same hash for metrics with identical parameters (excluding id).
        """
        config = {k: v for k, v in self.model_dump().items() if k != 'id'}
        config['_type'] = self.__class__.__name__  # Include class type
        
        # Use JSON with sorted keys for deterministic serialization
        config_str = json.dumps(config, sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()

    def __repr__(self) -> str:
        """Custom repr excluding the id field for consistent hash generation."""
        fields = {k: v for k, v in self.model_dump().items() if k != 'id'}
        fields_str = ', '.join(f"{k}={repr(v)}" for k, v in fields.items())
        return f"{self.__class__.__name__}({fields_str})"

class Categorical(Metric):
    categories: list[str]

class Continuous(Metric):
    min_value: float
    max_value: float

if __name__ == "__main__":

    cat_metric = Categorical(name="Sentiment", categories=["Positive", "Negative", "Neutral"])
    cont_metric = Continuous(name="Score", min_value=0.0, max_value=1.0)
    
    print(f"Categorical Metric: {repr(cat_metric)}")
    print(f"Continuous Metric: {repr(cont_metric)}")
    print(f"Categorical Metric Hash: {cat_metric._generate_config_hash()}")
    print(f"Continuous Metric Hash: {cont_metric._generate_config_hash()}")
    
    # Test that identical configs produce identical hashes
    cat_metric2 = Categorical(name="Sentiment", categories=["Positive", "Negative", "Neutral"])
    print(f"\nHash equality test:")

    print(f"cat_metric hash:  {cat_metric._generate_config_hash()}")
    print(f"cat_metric2 hash: {cat_metric2._generate_config_hash()}")
    print(f"Hashes are equal: {cat_metric._generate_config_hash() == cat_metric2._generate_config_hash()}")