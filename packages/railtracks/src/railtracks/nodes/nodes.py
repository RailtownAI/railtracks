from __future__ import annotations

import asyncio
import uuid
from abc import ABC, abstractmethod
from copy import deepcopy
from typing import Any, Generic, Literal, ParamSpec, TypeVar

from railtracks.llm.tools.tool import Tool
from railtracks.nodes.mappers import MapInputs, MapOutputs
from railtracks.nodes.wrappers import Wrapper
from railtracks.validation.node_creation.validation import (
    check_classmethod,
)

_TOutput = TypeVar("_TOutput")

_TNode = TypeVar("_TNode", bound="Node")


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


class DebugDetails(dict[str, Any]):
    """
    A simple debug detail object that operates like a dictionary that can be used to store debug information about
    the node.
    """

    pass


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

    frozen_wrappers: list[Wrapper[_P, _TOutput]] = []
    frozen_input_maps: list[MapInputs[tuple[list[Any], dict[str, Any]]]] = []
    frozen_output_maps: list[MapOutputs[_TOutput]] = []

    def __init__(
        self,
    ):
        # each fresh node will have a generated uuid that identifies it.
        self.uuid = str(uuid.uuid4())
        self.wrappers = deepcopy(self.frozen_wrappers)
        self.input_maps = deepcopy(self.frozen_input_maps)
        self.output_maps = deepcopy(self.frozen_output_maps)

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

        prelim_args, prelim_kwargs = args, kwargs
        for input_map in self.input_maps:
            prelim_args, prelim_kwargs = await input_map(*prelim_args, **prelim_kwargs)

        result: _TOutput = await invoke_method(*prelim_args, **prelim_kwargs)  # type: ignore

        for output_map in self.output_maps:
            result = await output_map(result)

        return result

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
    def prepare_args(cls, **kwargs) -> dict[str, Any]:
        """
        This method creates a new instance of the node by unpacking the tool parameters.

        If you would like any custom behavior please override this method.
        """
        return kwargs

    def safe_copy(self) -> Node[_P, _TOutput]:
        """
        Creates a copy of the node that is safe to pass across process barriers. This is done by creating a new instance
        of the node and copying over any relevant information. Note that this will not copy over any non picklable
        information such as open file handles or database connections.
        """
        cls = self.__class__
        result = cls.__new__(cls)  # type: ignore
        for key, value in self.__dict__.items():
            setattr(result, key, deepcopy(value))
        return result
