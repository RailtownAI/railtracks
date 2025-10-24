from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import (
    Coroutine,
    Generic,
    ParamSpec,
    Protocol,
    TypeVar,
)

from typing_extensions import Self

from railtracks.exceptions import NodeCreationError
from railtracks.llm import Tool
from railtracks.llm.type_mapping import TypeMapper
from railtracks.nodes.nodes import Node

_TOutput = TypeVar("_TOutput")
_P = ParamSpec("_P")


class DynamicFunctionNode(Node[_TOutput], ABC, Generic[_P, _TOutput]):
    """
    A base class which contains logic around converting function parameters to the required value given by the function.
    It also contains the framework for functionality of function nodes that can be built using the `from_function`
    method.

    NOTE: This class is not designed to be worked with directly. The classes SyncDynamicFunctionNode and
    AsyncDynamicFunctionNode are the ones designed for consumption.
    """

    def __init__(self, *args: _P.args, **kwargs: _P.kwargs):
        super().__init__()
        self.args = args
        self.kwargs = kwargs

    @classmethod
    @abstractmethod
    def func(
        cls, *args: _P.args, **kwargs: _P.kwargs
    ) -> _TOutput | Coroutine[None, None, _TOutput]:
        pass

    @classmethod
    def name(cls) -> str:
        return f"{cls.func.__name__}"

    @classmethod
    @abstractmethod
    def tool_info(cls) -> Tool:
        pass

    @classmethod
    @abstractmethod
    def type_mapper(cls) -> TypeMapper:
        pass

    @classmethod
    def prepare_tool(cls, **kwargs) -> Self:
        converted_params = cls.type_mapper().convert_kwargs_to_appropriate_types(kwargs)
        return cls(**converted_params)

    @classmethod
    def type(cls):
        return "Tool"


class SyncDynamicFunctionNode(DynamicFunctionNode[_P, _TOutput], ABC):
    """
    A nearly complete class that expects a synchronous function to be provided in the `func` method.

    The class' internals will handle the creation of the rest of the internals required for a node to operate.

    You can override methods like name and tool_info to provide custom names and tool information. However,
    do note that these overrides can cause unexpected behavior if not done according to what is expected in the parent
    class as it uses a lot of the structures in its implementation of other functions.
    """

    @classmethod
    @abstractmethod
    def func(cls, *args: _P.args, **kwargs: _P.kwargs) -> _TOutput:
        """
        The function that this node will call.
        This function should be synchronous.
        """
        pass

    async def invoke(self):
        result = await asyncio.to_thread(self.func, *self.args, **self.kwargs)

        # This is overly safe check to make sure the returned function isn't also a coroutine.

        # this would happen if some did the following
        # def function():
        #     async def inner_function():
        #         return "Hello"
        #     return inner_function

        if asyncio.iscoroutine(result):
            raise NodeCreationError(
                message="The function you provided was a coroutine in the clothing of a sync context. Please label it as an async function.",
                notes=[
                    "If your function returns a coroutine (e.g., calls async functions inside), refactor it to be async.",
                    "If you see this error unexpectedly, check if any library function you call is async.",
                ],
            )

        return result


class AsyncDynamicFunctionNode(
    DynamicFunctionNode[_P, _TOutput],
    ABC,
):
    """
    A nearly complete class that expects an async function to be provided in the `func` method.

    The class' internals will handle the creation of the rest of the internals required for a node to operate.

    You can override methods like name and tool_info to provide custom names and tool information. However,
    do note that these overrides can cause unexpected behavior if not done according to what is expected in the parent
    class as it uses a lot of the structures in its implementation of other functions.
    """

    @classmethod
    @abstractmethod
    async def func(cls, *args: _P.args, **kwargs: _P.kwargs) -> _TOutput:
        """
        The async function that this node will call.
        """
        pass

    async def invoke(self) -> _TOutput:
        return await self.func(*self.args, **self.kwargs)


class RTFunction(Protocol, Generic[_P, _TOutput]):
    """
    A protocol for a function (callable) which contains an additional parameter called node_type which contains the node representation of this function.
    """

    node_type: type[DynamicFunctionNode[_P, _TOutput]]

    def __call__(self, *args: _P.args, **kwargs: _P.kwargs) -> _TOutput: ...


class RTAsyncFunction(
    RTFunction[_P, Coroutine[None, None, _TOutput]], Generic[_P, _TOutput]
):
    """
    A protocol for an async function (callable) which contains an additional parameter called node_type which contains the node representation of this function.
    """

    node_type: AsyncDynamicFunctionNode[_P, _TOutput]


class RTSyncFunction(RTFunction[_P, _TOutput], Generic[_P, _TOutput]):
    """
    A protocol for a sync function (callable) which contains an additional parameter called node_type which contains the node representation of this function.
    """

    node_type: SyncDynamicFunctionNode[_P, _TOutput]
