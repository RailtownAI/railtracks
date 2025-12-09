import hashlib
from uuid import uuid4, UUID
from abc import ABC, abstractmethod
from typing import TypeVar, ParamSpec, Callable

from ...nodes.utils import Node
from ...built_nodes.concrete import RTFunction
from ...utils.point import AgentDataPoint

from ..data import DataPoint, Dataset


_P = ParamSpec("_P")
_TOutput = TypeVar("_TOutput")


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
    def run(self, data: DataPoint | list[DataPoint] | Dataset):
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


class OfflineEvaluator(Evaluator, ABC):
    """Evaluator that runs in an offline manner, typically involving
    batch processing of data without real-time interactions.
    """

    @abstractmethod
    def _transform(
        self,
        agent_data: list[AgentDataPoint] | None = None,
        agent_data_folder: str | None = None,
    ) -> Dataset | list[DataPoint]:
        """
        Transform the provided agent data points into the desired output format.
        """
        pass


class OnlineEvaluator(Evaluator, ABC):
    """Evaluator that runs in an online manner, typically involving
    real-time interactions with agents or models.
    """

    @abstractmethod
    def _call(
        self,
        agent: Callable[_P, Node[_TOutput] | RTFunction[_P, _TOutput]],
        data_point: list[DataPoint] | Dataset,
    ) -> _TOutput:
        """
        Run the provided agent on the given data point(s) and return the output.
        """
        pass
