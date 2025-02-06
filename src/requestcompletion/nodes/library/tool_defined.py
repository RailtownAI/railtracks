from ..nodes import Node
from ...llm import Tool

from typing import Generic, TypeVar, Dict, Any
from typing_extensions import Self

from abc import ABC, abstractmethod

_T = TypeVar("_T")


class ToolDefinedNode(Node[_T], ABC, Generic[_T]):
    @classmethod
    @abstractmethod
    def tool_info(cls) -> Tool:
        pass

    @classmethod
    @abstractmethod
    def prepare_tool(cls, tool_parameters: Dict[str, Any]) -> Self:
        pass
