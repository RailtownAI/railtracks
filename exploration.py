from __future__ import annotations

from typing import Callable, Literal, Type, TypeVar, Generic, ParamSpec, cast
from abc import ABC, abstractmethod

from railtracks.llm.history import MessageHistory
from railtracks.llm.message import AssistantMessage
from railtracks.llm.response import Response
from railtracks.llm.tools.parameters._base import Parameter

_P = ParamSpec("_P")
_T = TypeVar("_T")
_P2 = ParamSpec("_P2")
_T2 = TypeVar("_T2")


def unpack(item: _T | None  ,/) -> _T:
    if item is None:
        raise ValueError("Unpacked Item was None")
    return item

def safe_create_node(class_name: str | None, required_methods: dict[str, Callable[...] | classmethod], optional_methods: dict[str, Callable[...] | classmethod]) -> Type[Node]:
    if class_name is None:
        raise ValueError("Class name cannot be None")
    
    for method_name in required_methods.keys():
        if method_name in optional_methods:
            raise ValueError(f"Required Method shares a name with an optional method: {method_name}")
        
    class_dict = {**required_methods, **optional_methods}

    return type(class_name, (Node,), class_dict)

class NodeBuilder(Generic[_P, _T]):
    def __init__(self) -> None:
        self._invoke: Callable[_P, _T] | None = None
        self._node_class: Literal["tool", "llm"] | None = None
        self.node_name: str | None = None

        self.paramater: Parameter | None = None

    @classmethod
    def llm(cls, structured: bool, tool_call: bool) -> NodeBuilder[_P, _T]:
        # TODO: implement functionality to build functionality of the base type
        return cls()

    @classmethod
    def function(cls, function: Callable[_P2, _T2]) -> NodeBuilder[_P2, _T2]:
        instance = cls()
        casted_instance = cast(NodeBuilder[_P2, _T2], instance)
        casted_instance._invoke = function
        casted_instance._node_class = "tool"
        casted_instance.node_name = function.__name__
        
        return casted_instance

    def construct_required(self) -> dict[str, Callable[...] | classmethod]:
        return {
            "invoke": lambda _self, *args, **kwargs: unpack(self._invoke)(*args, **kwargs),
            "type": classmethod(lambda _cls: unpack(self._node_class)),
        }
    
    def construct_optional(self) -> dict[str, Callable[...] | classmethod]:
        return {}

    def build(self) -> Type[Node[_P, _T]]:
        return safe_create_node(
            self.node_name,
            self.construct_required(),
            self.construct_optional(),
        )
        
# TODO: add over loads here for structured response types

def llm_invoke_factory(
        structured: bool,
        llm_call: Callable[[MessageHistory], AssistantMessage]
    ) -> Callable[[MessageHistory], Response]:
    pass
    
def llm_model_call_factory(
    
) -> Callable[[MessageHistory], Response]:
    pass
    

class Node(ABC, Generic[_P, _T]):
    def __init__(self) -> None:
        pass

    @abstractmethod
    def invoke(self, *args: _P.args, **kwargs: _P.kwargs) -> _T:
        pass

    @classmethod
    @abstractmethod
    def type(cls) -> Literal["Tool", "Agent", "Other"]:
        pass








if __name__ == "__main__":
    def some_function() -> str:
        return "Hello, World!"
    
    FunctionType = NodeBuilder.function(some_function).build()

    result = FunctionType().invoke()

    print(result)
    print(FunctionType.type())


