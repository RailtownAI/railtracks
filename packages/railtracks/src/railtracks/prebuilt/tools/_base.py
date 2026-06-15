from abc import ABC, abstractmethod
from typing import Iterable


from railtracks.built_nodes.concrete.function_base import RTFunction
from typing_extensions import Self


class ToolSet(ABC):

    @abstractmethod
    @classmethod
    def prompt(cls) -> str:
        """Mutilple short sentances guiding the agent"""

    @abstractmethod
    @classmethod
    def create(cls, *args, **kwargs) -> Iterable[RTFunction]:
        pass

    

