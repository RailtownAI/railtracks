from __future__ import annotations

from os import name
from typing import Any, Callable, Literal, Type, TypeVar, Generic, ParamSpec, cast
from abc import ABC, abstractmethod

from railtracks.llm.tools.tool import Tool
from railtracks.llm.type_mapping import TypeMapper

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



import asyncio
import time
import uuid
from abc import ABC, abstractmethod
from copy import deepcopy
from typing import Any, Callable, Dict, Generic, Literal, ParamSpec, TypeVar

from railtracks.llm.tools.tool import Tool

from typing_extensions import Self

from railtracks.validation.node_creation.validation import (
    check_classmethod,
)


_TOutput = TypeVar("_TOutput")

_TNode = TypeVar("_TNode", bound="Node")
from typing import Any, Callable, Coroutine, Generic, ParamSpec, Protocol, TypeVar

_P = ParamSpec("_P")
_T = TypeVar("_T")


class Wrapper(Protocol, Generic[_P, _T]):
    def __call__(
        self, function: Callable[_P, Coroutine[Any, Any, _T]]
    ) -> Callable[_P, Coroutine[Any, Any, _T]]: ...

class NodeState(Generic[_TNode]):
    """
    A stripped down representation of a Node which can be passed along the process barrier.
    """

    # This object should json serializable such that it can be passed across the process barrier
    # TODO come up with a more intelligent way to recreate the node
    def __init__(
        self,
        node: _TNode,
    ):
        self.node = node

    def instantiate(self) -> _TNode:
        """
        Creates a pass by reference copy of the node in the state.
        """
        return self.node


class LatencyDetails:
    def __init__(
        self,
        total_time: float,
    ):
        """
        A simple class that contains latency details for a node during execution.

        Args:
            total_time (float): The total time taken for the node to execute, in seconds.
        """
        self.total_time = total_time


_P = ParamSpec("_P")


class Node(ABC, Generic[_P, _TOutput]):
    """An abstract base class which defines some the functionality of a node"""

    def __init_subclass__(cls):
        # now we need to make sure the invoke method is a coroutine, if not we should automatically switch it here.
        method_name = "invoke"

        if method_name in cls.__dict__ and callable(cls.__dict__[method_name]):
            method = cls.__dict__[method_name]

            # a simple wrapper to convert any async function to a non async one.
            async def async_wrapper(self, *args, **kwargs):
                if asyncio.iscoroutinefunction(
                    method
                ):  # check if the method is a coroutine
                    return await method(self, *args, **kwargs)
                else:
                    return await asyncio.to_thread(method, self, *args, **kwargs)

            setattr(cls, method_name, async_wrapper)

        # ================= Checks for Creation ================
        # 1. Check if the class methods are all classmethods, else raise an exception
        class_method_checklist = ["tool_info", "prepare_tool", "name"]
        for method_name in class_method_checklist:
            if method_name in cls.__dict__ and callable(cls.__dict__[method_name]):
                method = cls.__dict__[method_name]
                check_classmethod(method, method_name)

        # without this direct call to the parent __init_subclass__ method the generic resolutions will not work correctly
        super().__init_subclass__()

    wrappers: list[Wrapper[_P, _TOutput]] = []

    def __init__(
        self,
    ):
        # each fresh node will have a generated uuid that identifies it.
        self.uuid = str(uuid.uuid4())

    @classmethod
    @abstractmethod
    def name(cls) -> str:
        """
        Returns a pretty name for the node. This name is used to identify the node type of the system.
        """
        pass

    @abstractmethod
    async def invoke(self, *args: _P.args, **kwargs: _P.kwargs) -> _TOutput:
        """
        The main method that runs when this node is called
        """
        pass

    async def wrapped_invoke(self, *args: _P.args, **kwargs: _P.kwargs) -> _TOutput:
        """
        A special method that will track and save the latency of the running of this invoke method.
        """
        invoke_method = self.invoke
        for wrapper in self.wrappers:
            invoke_method = wrapper(invoke_method)

        return await invoke_method(*args, **kwargs)

    def __repr__(self):
        return f"{self.name()} <{hex(id(self))}>"

    @classmethod
    @abstractmethod
    def type(cls) -> Literal["Tool", "Agent", "Other"]:
        pass

    @classmethod
    def tool_info(cls) -> Tool:
        """
        A method used to provide information about the node in the form of a tool definition.
        This is commonly used with LLMs Tool Calling tooling.
        """
        # TODO: this should default to interfacing within the init method of the class
        raise NotImplementedError(
            "You must implement the tool_info method in your node"
        )

    @classmethod
    def prepare_arguments(cls, **kwargs) -> dict[str, Any]:
        """
        This method creates a new set of arguments for the node by unpacking the tool parameters.

        If you would like any custom behavior please override this method.
        """
        return kwargs


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
