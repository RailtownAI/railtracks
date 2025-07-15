from __future__ import annotations

import asyncio
import time
import uuid
from abc import ABC, ABCMeta, abstractmethod
from copy import deepcopy
from typing import (
    Any,
    Dict,
    Generic,
    ParamSpec,
    TypeVar,
)

from typing_extensions import Self

from ..exceptions.node_creation.validation import (
    check_classmethod,
    check_connected_nodes,
    check_output_model,
)
from ..llm import Tool

_TOutput = TypeVar("_TOutput")

_TNode = TypeVar("_TNode", bound="Node")
_P = ParamSpec("_P")


class NodeCreationMeta(ABCMeta):
    def __init__(cls, name, bases, dct):
        super().__init__(name, bases, dct)

        # now we need to make sure the invoke method is a coroutine, if not we should automatically switch it here.
        method_name = "invoke"

        if method_name in dct and callable(dct[method_name]):
            method = dct[method_name]

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
        class_method_checklist = ["tool_info", "prepare_tool", "pretty_name"]
        for method_name in class_method_checklist:
            if method_name in dct and callable(dct[method_name]):
                method = dct[method_name]
                check_classmethod(method, method_name)

        # 2. special case for output_model for structured_llm node
        if "output_model" in dct and not getattr(cls, "__abstractmethods__", False):
            method = dct["output_model"]
            check_classmethod(method, "output_model")
            check_output_model(method, cls)

        # 3. Check if the connected_nodes is not empty, special case for ToolCallLLM
        if "connected_nodes" in dct and not getattr(cls, "__abstractmethods__", False):
            method = dct["connected_nodes"]
            try:
                # Try to call the method as a classmethod (typical case)
                node_set = method.__func__(cls)
            except AttributeError:
                # If that fails, call it as an instance method (for easy_wrapper init)
                dummy = object.__new__(cls)
                node_set = method(dummy)
            # Validate that the returned node_set is correct and contains only Node/function instances
            check_connected_nodes(node_set, Node)
        # ================= End Creation Exceptions ================


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


class Node(ABC, Generic[_TOutput], metaclass=NodeCreationMeta):
    """An abstract base class which defines some the functionality of a node"""

    def __init__(
        self,
        *,
        debug_details: DebugDetails | None = None,
    ):
        # each fresh node will have a generated uuid that identifies it.
        self.uuid = str(uuid.uuid4())
        self._details: DebugDetails = debug_details or DebugDetails()

    @property
    def details(self) -> DebugDetails:
        """
        Returns a debug details object that contains information about the node.
        This is used for debugging and logging purposes.
        """
        return self._details

    @classmethod
    @abstractmethod
    def pretty_name(cls) -> str:
        """
        Returns a pretty name for the node. This name is used to identify the node type of the system.
        """
        pass

    @abstractmethod
    async def invoke(self) -> _TOutput:
        """
        The main method that runs when this node is called
        """
        pass

    async def tracked_invoke(self) -> _TOutput:
        """
        A special method that will track and save the latency of the running of this invoke method.
        """
        start_time = time.time()
        try:
            return await self.invoke()
        except Exception as e:
            raise e
        finally:
            latency = time.time() - start_time
            self.details["latency"] = LatencyDetails(total_time=latency)

    def state_details(self) -> Dict[str, str]:
        """
        Places the __dict__ of the current object into a dictionary of strings.
        """
        di = {k: str(v) for k, v in self.__dict__.items()}
        return di

    @classmethod
    def tool_info(cls) -> Tool:
        """
        A method used to provide information about the node in the form of a tool definition.
        This is commonly used with LLMs Tool Calling tooling.
        """
        # TODO: finish implementing this method
        raise NotImplementedError(
            "You must implement the tool_info method in your node"
        )

    @classmethod
    def prepare_tool(cls, tool_parameters: Dict[str, Any]) -> Self:
        """
        This method creates a new instance of the node by unpacking the tool parameters.

        If you would like any custom behavior please override this method.
        """
        return cls(**tool_parameters)  # noqa

    def safe_copy(self) -> Self:
        """
        A method used to create a new pass by value copy of every element of the node except for the backend connections.
        """
        cls = self.__class__
        result = cls.__new__(cls)
        for k, v in self.__dict__.items():
            setattr(result, k, deepcopy(v))
        return result

    def __repr__(self):
        return f"{hex(id(self))}: {self.pretty_name()}: {self.state_details()}"
