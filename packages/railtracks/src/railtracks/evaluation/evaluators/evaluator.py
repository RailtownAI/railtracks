import hashlib
from uuid import uuid4, UUID
from abc import ABC, abstractmethod

from ... import AgentDataPoint
from ..data import DataPoint, Dataset

class Evaluator(ABC):
    def __init__(self):
        self._id: UUID = uuid4()
        self._config_hash: str = self._generate_unique_hash()

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def config_hash(self) -> str:
        return self._config_hash

    @abstractmethod
    def run(self, data: AgentDataPoint | list[AgentDataPoint] | Dataset):
        pass

    def _generate_unique_hash(self) -> str:
        """Generate a deterministic hash based on evaluator configuration.

        This should create a hash-based identifier that remains consistent
        for evaluators with identical configurations, enabling equality
        comparisons across different instances.

        Note: Overload the __repr__ method in subclasses to ensure all relevant
        configuration details are included in the string representation.
        """
        str_repr = repr(self)
        return hashlib.sha256(str_repr.encode()).hexdigest()