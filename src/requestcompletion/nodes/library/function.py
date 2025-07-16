from __future__ import annotations

import asyncio
import inspect
import types
from abc import abstractmethod, ABC
from typing import (
    Any,
    Callable,
    Coroutine,
    Dict,
    Generic,
    List,
    ParamSpec,
    Tuple,
    Type,
    TypeVar,
    Union,
    get_args,
    get_origin, overload,
)

import typing_extensions
from pydantic import BaseModel
from typing_extensions import Self

from ...exceptions import NodeCreationError
from ...exceptions.node_creation.validation import validate_function
from ...llm.tools import Tool
from ...llm.tools.parameter_handlers import UnsupportedParameterError
from ..nodes import Node

_TOutput = TypeVar("_TOutput")
_P = ParamSpec("_P")


def to_node(func):
    """Decorator to convert a function into a Node using from_function."""
    return from_function(func)

class DynamicFunctionNode(Node[_TOutput], Generic[_P, _TOutput], ABC):
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
    def _convert_kwargs_to_appropriate_types(cls, kwargs) -> Dict[str, Any]:
        """Convert kwargs to appropriate types based on function signature."""
        converted_kwargs = {}

        try:
            sig = inspect.signature(cls.func)

        except ValueError:
            raise RuntimeError(
                "Cannot convert kwargs for builtin functions. "
                "Please use a custom function."
            )

        # Process all parameters from the function signature
        for param_name, param in sig.parameters.items():
            # If the parameter is in kwargs, convert it
            if param_name in kwargs:
                converted_kwargs[param_name] = cls._convert_value(
                    kwargs[param_name], param.annotation, param_name
                )

        return converted_kwargs


    @classmethod
    def _convert_value(
            cls, value: Any, target_type: Any, param_name: str = "unknown"
    ) -> Any:
        """
        Convert a value to the target type based on type annotation.

        Args:
            value: The value to convert
            target_type: The target type annotation
            param_name: The name of the parameter (for error reporting)

        Returns:
            The converted value
        """
        # If the value is None or the target_type is one of Any or inspect._empty, return as is since there is nothing to convert to
        if value is None or target_type is Any or target_type is inspect._empty:
            return value

        # Handle Pydantic models
        if inspect.isclass(target_type) and issubclass(target_type, BaseModel):
            return cls._convert_to_pydantic_model(value, target_type)

        # Get the origin type (for generics like List, Dict, etc.)
        origin = get_origin(target_type)
        args = get_args(target_type)

        # Handle dictionary types - raise UnsupportedParameterException
        if origin in (dict, Dict):
            param_type = str(target_type)
            raise UnsupportedParameterError(param_name, param_type)

        # Handle sequence types (lists and tuples) consistently
        if origin in (list, tuple):
            return cls._convert_to_sequence(value, origin, args)

        # For primitive types, try direct conversion
        try:
            # Only attempt conversion for basic types, not for complex types
            if inspect.isclass(target_type) and not hasattr(
                    target_type, "__origin__"
            ):
                return target_type(value)
        except (TypeError, ValueError):
            return "Tool call parameter type conversion failed."

        # If conversion fails or isn't applicable, return the original value
        return value

    @classmethod
    def _convert_to_pydantic_model(
            cls, value: Any, model_class: Type[BaseModel]
    ) -> Any:
        """Convert a value to a Pydantic model."""
        if isinstance(value, dict):
            return model_class(**value)
        raise UnsupportedParameterError(str(value), str(type(value)))

    @classmethod
    def _convert_to_sequence(
            cls, value: Any, target_type: Type, type_args: Tuple[Type, ...]
    ) -> Union[List[Any], Tuple[Any, ...]]:
        """
        Convert a value to a sequence (list or tuple) with the expected element types.

        Args:
            value: The value to convert
            target_type: The target sequence type (list or tuple)
            type_args: The type arguments for the sequence elements

        Returns:
            The converted sequence
        """
        # If it's any kind of sequence (list or tuple), process each element
        if isinstance(value, (list, tuple)):
            # Convert each element to the appropriate type
            result = [
                cls._convert_element(item, type_args, i)
                for i, item in enumerate(value)
            ]
            # Return as the target type (list or tuple)
            return tuple(result) if target_type is tuple else result

        # For any non-sequence type, wrap in a sequence with a single element
        result = [cls._convert_element(value, type_args, 0)]
        return tuple(result) if target_type is tuple else result

    @classmethod
    def _convert_element(
            cls, value: Any, type_args: Tuple[Type, ...], index: int
    ) -> Any:
        """
        Convert a sequence element to the expected type.

        Args:
            value: The value to convert
            type_args: The type arguments for the sequence elements
            index: The index of the element in the sequence

        Returns:
            The converted element
        """
        # Determine the appropriate type for this element
        if not type_args:
            # No type information available, return as is
            return value
        elif index < len(type_args):
            # For tuples with heterogeneous types, use the type at the corresponding index
            element_type = type_args[index]
        else:
            # For lists or when index exceeds available types, use the first type
            # (Lists typically have a single type argument that applies to all elements)
            element_type = type_args[0]

        # Convert the value to the determined type
        return cls._convert_value(value, element_type)


    @classmethod
    @abstractmethod
    def func(cls, *args: _P.args, **kwargs: _P.kwargs) -> _TOutput | Coroutine[None, None, _TOutput]:
        pass
        

    @classmethod
    def pretty_name(cls) -> str:
        return f"{cls.func.__name__} Node"

    @classmethod
    def tool_info(cls) -> Tool:
        return Tool.from_function(cls.func)

    @classmethod
    def prepare_tool(cls, tool_parameters: Dict[str, Any]) -> Self:
        converted_params = cls._convert_kwargs_to_appropriate_types(tool_parameters)
        return cls(**converted_params)


class SyncDynamicFunctionNode(DynamicFunctionNode[_P, _TOutput], Generic[_P, _TOutput], ABC):
    @classmethod
    @abstractmethod
    def func(cls, *args: _P.args, **kwargs: _P.kwargs) -> _TOutput:
        """
        The function that this node will call.
        This function should be synchronous.
        """
        pass

    async def invoke(self):
            result = self.func(*self.args, **self.kwargs)

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

class AsyncDynamicFunctionNode(DynamicFunctionNode[_P, _TOutput], Generic[_P, _TOutput], ABC):
    """
    A nearly complete class that expects an async function to be provided in the `func` method.

    The class' internals will handle the creation of the rest of the internals required for a node to operate.

    You can override methods like pretty_name and tool_info to provide custom names and tool information. However,
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




def from_function(
    func: Callable[[_P], Coroutine[None, None, _TOutput] | _TOutput],
):
    """
    Creates a new Node type from a function that can be used in `rc.call()`.
    """
    builder = NodeBuilder()


@typing_extensions.deprecated("The function node is deprecated use DynamicFunctionNode instead.")
class FunctionNode(Node[_TOutput]):
    """
    A class for ease of creating a function node for the user
    """

    def __init__(
        self,
        func: Callable[[_P], Coroutine[None, None, _TOutput] | _TOutput],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    async def invoke(self) -> _TOutput:
        result = self.func(*self.args, **self.kwargs)
        if asyncio.iscoroutine(self.func):
            await result

        return result

    @classmethod
    def pretty_name(cls) -> str:
        return f"Function Node - {cls.__class__.__name__}"

    @classmethod
    def tool_info(cls) -> Tool:
        return Tool.from_function(cls.func)

    @classmethod
    def prepare_tool(cls, tool_parameters):
        return cls(**tool_parameters)
