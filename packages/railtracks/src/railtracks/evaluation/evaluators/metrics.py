from dataclasses import dataclass
import hashlib
from pydantic import BaseModel

class Metric(BaseModel):
    name: str

    def _generate_unique_hash(self) -> str:
        return hashlib.sha256(repr(self).encode()).hexdigest()

class Categorical(Metric):
    categories: list[str]

class Continuous(Metric):
    min_value: float
    max_value: float

if __name__ == "__main__":

    cat_metric = Categorical(name="Sentiment", categories=["Positive", "Negative", "Neutral"])
    cont_metric = Continuous(name="Score", min_value=0.0, max_value=1.0)
    
    print(f"Categorical Metric Hash: {cat_metric._generate_unique_hash()}")
    print(f"Continuous Metric Hash: {cont_metric._generate_unique_hash()}")