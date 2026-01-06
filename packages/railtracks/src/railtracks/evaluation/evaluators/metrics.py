import hashlib
import json
from pydantic import BaseModel, Field, field_validator, model_validator
from uuid import UUID, uuid4
from collections import defaultdict

class Metric(BaseModel):
    name: str
    # identifier: UUID = Field(default_factory=uuid4)
    identifier: str = Field(default_factory=lambda: str(uuid4()))
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
    
    def __str__(self) -> str:
        """Clean string representation excluding identifier and config_hash."""
        fields = {k: v for k, v in self.model_dump().items() if k not in ('identifier', 'config_hash')}
        fields_str = ', '.join(f"{k}={repr(v)}" for k, v in fields.items())
        return f"{self.__class__.__name__}({fields_str})"

class Categorical(Metric):
    categories: list[str]

# class CategoricalAggregate(Metric):
#     metrics: list[tuple[Categorical, str]] # The str corresponds to the label chosen
#     most_common: dict[str, str] = Field(default_factory=dict)
#     least_common: dict[str, str] = Field(default_factory=dict)
#     counts: dict[str, dict[str, int]] = Field(default_factory=dict)

#     def model_post_init(self, __context) -> None:
#         """Aggregate categories from the provided metrics."""
        
#         for metric, metric_label in self.metrics:
#             if metric.name not in self.counts:
#                 self.counts[metric.name] = defaultdict(int)
#             self.counts[metric.name][metric_label] += 1

#         for metric_name, label_counts in self.counts.items():
#             sorted_labels = sorted(label_counts.items(), key=lambda item: item[1], reverse=True)
#             self.most_common[metric_name] = sorted_labels[0][0]
#             self.least_common[metric_name] = sorted_labels[-1][0]

class CategoricalAggregate(Metric):
    metric: Categorical 
    labels: list[str]
    #     most_common: dict[str, str] = Field(default_factory=dict)
    #     least_common: dict[str, str] = Field(default_factory=dict)
    #     counts: dict[str, dict[str, int]] = Field(default_factory=dict)
    def model_post_init(self, __context) -> None:
        """Aggregate categories from the provided metrics."""

        for label in self.labels:
            if label not in self.metric.categories:
                raise Exception("Unknown label")




class Numerical(Metric):
    min_value: int | float | None = None
    max_value: int | float | None = None
    # value: int | float

    # @model_validator(mode='after')
    # def validate_value(self):
    #     """Validate that value is within min and max bounds if they are set."""
    #     if self.min_value is not None and self.value < self.min_value:
    #         raise ValueError(f"Value {self.value} is less than minimum allowed {self.min_value}.")
    #     if self.max_value is not None and self.value > self.max_value:
    #         raise ValueError(f"Value {self.value} is greater than maximum allowed {self.max_value}.")
    #     return self
    
if __name__ == "__main__":
    # Example usage and testing of Metric classes
    cat_metric1 = Categorical(name="Sentiment", categories=["Positive", "Negative", "Neutral"])
    cat_metric2 = Categorical(name="Helpfulness", categories=["Helpful", "Unhelpful"])