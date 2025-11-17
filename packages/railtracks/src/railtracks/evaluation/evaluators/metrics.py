from pydantic import BaseModel

class Metric(BaseModel):
    name: str


class Categorical(Metric):
    categories: list[str]

class Continuous(Metric):
    min_value: float
    max_value: float