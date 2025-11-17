from dataclasses import dataclass

@dataclass(frozen=True)
class DataPoint:
    """A class representing a single data point"""
    input_data: str
    expected_output: str
    metadata: dict | None = None