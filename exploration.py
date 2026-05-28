from __future__ import annotations

from os import name
from typing import Any, Callable, Literal, Type, TypeVar, Generic, ParamSpec, cast
from abc import ABC, abstractmethod

from railtracks.llm.history import MessageHistory
from railtracks.llm.message import AssistantMessage
from railtracks.llm.response import Response
from railtracks.llm.tools.parameters._base import Parameter
from railtracks.llm.tools.tool import Tool
from railtracks.llm.type_mapping import TypeMapper
from railtracks.nodes.nodes import Node

_P = ParamSpec("_P")
_T = TypeVar("_T")
_P2 = ParamSpec("_P2")
_T2 = TypeVar("_T2")


def unpack(item: _T | None, /) -> _T:
    if item is None:
        raise ValueError("Unpacked Item was None")
    return item


def safe_create_node(
    class_name: str | None,
    required_methods: dict[str, Callable[...] | classmethod],
    optional_methods: dict[str, Callable[...] | classmethod | None],
) -> Type[Node]:
    if class_name is None:
        raise ValueError("Class name cannot be None")

    for method_name in required_methods.keys():
        if method_name in optional_methods:
            raise ValueError(
                f"Required Method shares a name with an optional method: {method_name}"
            )

    for method_name in optional_methods.keys():
        if optional_methods[method_name] is None:
            del optional_methods[method_name]

    class_dict = {**required_methods, **optional_methods}

    return type(class_name + "Node", (Node,), class_dict)


class NodeBuilder(Generic[_P, _T]):
    def __init__(self) -> None:
        self._invoke: Callable[_P, _T] | None = None
        self._node_class: Literal["Tool", "Agent"] | None = None
        self._node_name: str | None = None

        self._tool_info: Callable[[], Tool] | None = None
        self._prepare_arguments: Callable[..., dict[str, Any]] | None = None

    @classmethod
    def llm(cls, structured: bool, tool_call: bool) -> NodeBuilder[_P, _T]:
        # TODO: implement functionality to build functionality of the base type
        return cls()

    @classmethod
    def function(
        cls,
        function: Callable[_P2, _T2],
        name: str | None = None,
    ) -> NodeBuilder[_P2, _T2]:
        instance = cls()
        casted_instance = cast(NodeBuilder[_P2, _T2], instance)
        casted_instance._invoke = function
        casted_instance._node_class = "Tool"
        casted_instance._node_name = name or function.__name__

        tm = TypeMapper(function)
        tool = Tool.from_function(function)
        casted_instance._tool_info = lambda: tool

        casted_instance._prepare_arguments = tm.convert_kwargs_to_appropriate_types

        return casted_instance

    def construct_required(self) -> dict[str, Callable[...] | classmethod]:
        return {
            "invoke": lambda _self, *args, **kwargs: unpack(self._invoke)(
                *args, **kwargs
            ),
            "type": classmethod(lambda _cls: unpack(self._node_class)),
            "name": classmethod(lambda _cls: unpack(self._node_name)),
        }

    def construct_optional(self) -> dict[str, Callable[...] | classmethod | None]:
        return {
            "tool_info": self._construct_tool_info(),
            "prepare_arguments": self._construct_prepared_arguments(),
        }
    
    def _construct_prepared_arguments(self, **kwargs):
        if self._prepare_arguments is None:
            return None
        
        return classmethod(
                lambda _cls, **kwargs: unpack(self._prepare_arguments)(**kwargs)
            )
    
    def _construct_tool_info(self):
        if self._tool_info is None:
            return None
        
        return classmethod(lambda _cls: unpack(self._tool_info))
            


    def build(self) -> Type[Node[_P, _T]]:
        return safe_create_node(
            self._node_name,
            self.construct_required(),
            self.construct_optional(),
        )


# TODO: add over loads here for structured response types

# def llm_invoke_factory(
#         structured: bool,
#         llm_call: Callable[[MessageHistory], AssistantMessage]
#     ) -> Callable[[MessageHistory], Response]:
#     pass

# def llm_model_call_factory(

# ) -> Callable[[MessageHistory], Response]:
#     pass


if __name__ == "__main__":

    def some_function() -> str:
        """
        A simple function that returns a string.
        """
        return "Hello, World!"

    FunctionType = NodeBuilder.function(some_function).build()

    result = FunctionType().invoke()

    print(result)
    print(FunctionType.type())
    print(FunctionType.tool_info())
