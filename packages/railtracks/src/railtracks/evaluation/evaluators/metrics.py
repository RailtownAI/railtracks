import hashlib
import json
from pydantic import BaseModel, Field, model_validator
from uuid import UUID, uuid4

class Metric(BaseModel):
    name: str
    identifier: UUID = Field(default_factory=uuid4)
    config_hash: str = ""

    @model_validator(mode='after')
    def _set_config_hash(self):
        """Generate a deterministic hash based on metric configuration.
        This method sets the _config_hash attribute and _id is exluded from the hash calculation.
        """
        config = {k: v for k, v in self.model_dump().items() if k != 'identifier'}
        config['_type'] = self.__class__.__name__
        
        config_str = json.dumps(config, sort_keys=True)
        self.config_hash = hashlib.sha256(config_str.encode()).hexdigest()
        return self

    def __repr__(self) -> str:
        """Custom repr excluding the id field for consistent hash generation."""
        fields = {k: v for k, v in self.model_dump().items() if k != 'id'}
        fields_str = ', '.join(f"{k}={repr(v)}" for k, v in fields.items())
        return f"{self.__class__.__name__}({fields_str})"

class Categorical(Metric):
    categories: list[str]

class Numberical(Metric):
    min_value: float
    max_value: float

if __name__ == "__main__":
    # Example usage and testing of Metric classes
    cat_metric1 = Categorical(name="Sentiment", categories=["Positive", "Negative", "Neutral"])
    cat_metric2 = Categorical(name="Sentiment", categories=["Positive", "Negative", "Neutral"])
    num_metric = Numberical(name="Accuracy", min_value=0.0, max_value=1.0)

    print("Categorical Metric 1 ID:", cat_metric1.identifier)
    print("Categorical Metric 1 Config Hash:", cat_metric1.config_hash)
    print("Categorical Metric 1 repr output:", repr(cat_metric1), end="\n\n")
    
    print("Categorical Metric 2 ID:", cat_metric2.identifier)
    print("Categorical Metric 2 Config Hash:", cat_metric2.config_hash)
    print("Categorical Metric 2 repr output:", repr(cat_metric2), end="\n\n")
    
    print("Numerical Metric ID:", num_metric.identifier)
    print("Numerical Metric Config Hash:", num_metric.config_hash)
    print("Numerical Metric repr output:", repr(num_metric), end="\n\n")
    
    assert cat_metric1.config_hash == cat_metric2.config_hash, "Config hashes should match for identical metrics"
    assert cat_metric1.identifier != cat_metric2.identifier, "IDs should be unique per instance"