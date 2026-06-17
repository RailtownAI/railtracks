from abc import ABC, abstractmethod
from typing import Iterable

from railtracks.built_nodes.concrete.function_base import RTFunction


class ToolSet(ABC):
    @classmethod
    @abstractmethod
    def prompt(cls) -> str:
        """Mutilple short sentances guiding the agent"""

    @abstractmethod
    def tool_set(self) -> Iterable[RTFunction]:
        pass
