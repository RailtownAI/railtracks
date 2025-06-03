from __future__ import annotations

import asyncio
import uuid
from copy import deepcopy

from ..llm import Tool

from abc import ABC, abstractmethod, ABCMeta
import inspect

from typing import (
    TypeVar,
    Generic,
    Dict,
    ParamSpec,
    Any,
    Coroutine,
)

from typing_extensions import Self


_TOutput = TypeVar("_TOutput")


_TNode = TypeVar("_TNode", bound="Node")
_P = ParamSpec("_P")


class EnsureInvokeCoroutineMeta(ABCMeta):
    def __init__(cls, name, bases, dct):
        super().__init__(name, bases, dct)

        # now we need to make sure the invoke method is a coroutine, if not we should automatically switch it here.
        method_name = "invoke"
        if method_name in dct and callable(dct[method_name]):
            method = dct[method_name]
            if not inspect.iscoroutinefunction(method):
                # a simple async wrapper of the sequential method.
                async def async_wrapper(self, *args, **kwargs):
                    return await asyncio.to_thread(method(self, *args, **kwargs))

                setattr(cls, method_name, async_wrapper)


# TODO add generic for required context object
class Node(ABC, Generic[_TOutput], metaclass=EnsureInvokeCoroutineMeta):
    """An abstract base class which defines some the functionality of a node"""

    def __init__(
        self,
    ):
        # each fresh node will have a generated uuid that identifies it.
        self.uuid = str(uuid.uuid4())

    @classmethod
    @abstractmethod
    def pretty_name(cls) -> str:
        """
        Returns a pretty name for the node. This name is used to identify the node type of the system.
        """

    @abstractmethod
    async def invoke(self) -> Coroutine[Any, Any, _TOutput]:
        """
        The main method that runs when this node is called
        """
        pass

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
        # detail = inspect.getdoc(cls)
        # if detail is None:
        #     warnings.warn(f"Node {cls.__name__} does not have a docstring. Using empty string instead.")
        #     detail = ""
        #
        # params = inspect.signature(cls.__init__).parameters
        #
        # tool = Tool(
        #     name=cls.pretty_name(),
        #     detail=detail,
        #     parameters=set(
        #         [
        #             Parameter(name=k, description=v.annotation, param_type="string")
        #             for k, v in params.items()
        #             if k != "self"
        #         ]
        #     ),
        # )

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

        The backend connections include the data streamer, create_node_hook and invoke_node_hook.

        """
        cls = self.__class__
        result = cls.__new__(cls)
        for k, v in self.__dict__.items():
            setattr(result, k, deepcopy(v))
        return result
