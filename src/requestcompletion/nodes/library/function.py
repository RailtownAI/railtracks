from __future__ import annotations

from typing_extensions import Self
import warnings

from ...llm.tools import Tool
from ...llm.tools.parameter_handlers import UnsupportedParameterException

from typing import (
    Any,
    TypeVar,
    Callable,
    List,
    Dict,
    Type,
    Dict,
    Optional,
    Tuple,
    Union,
    get_origin,
    get_args,
)

from ..nodes import Node, Tool
import inspect
from pydantic import BaseModel


_TOutput = TypeVar("_TOutput")


def from_function(func: Callable) -> Type[Node]:
    """
    A function to create a node from a function
    """

    class DynamicFunctionNode(Node):
        def __init__(self, *args, **kwargs):
            super().__init__()
            self.args = args
            self.kwargs = kwargs

        def invoke(self) -> Any:
            """Invoke the function with converted arguments."""
            try:
                # Convert kwargs to appropriate types based on function signature
                converted_kwargs = self._convert_kwargs_to_appropriate_types()

                # Call the function with converted arguments
                result = func(*self.args, **converted_kwargs)
                return result
            except Exception as e:
                warnings.warn(
                    f"Error invoking function {func.__name__}\nProvidedArgs: {self.args}\nProvided kwargs:\n{self.kwargs}.\n: {str(e)}")
                raise e

        def _convert_kwargs_to_appropriate_types(self) -> Dict[str, Any]:
            """Convert kwargs to appropriate types based on function signature."""
            converted_kwargs = {}
            sig = inspect.signature(func)

            # Process all parameters from the function signature
            for param_name, param in sig.parameters.items():
                # If the parameter is in kwargs, convert it
                if param_name in self.kwargs:
                    converted_kwargs[param_name] = self._convert_value(
                        self.kwargs[param_name], param.annotation, param_name
                    )

            return converted_kwargs

        def _convert_value(self, value: Any, target_type: Any, param_name: str = "unknown") -> Any:
            """
            Convert a value to the target type based on type annotation.

            Args:
                value: The value to convert
                target_type: The target type annotation
                param_name: The name of the parameter (for error reporting)

            Returns:
                The converted value
            """
            # If the value is None or the target_type is Any, return as is
            if value is None or target_type is Any:
                return value

            # Handle Pydantic models
            if inspect.isclass(target_type) and issubclass(target_type, BaseModel):
                return self._convert_to_pydantic_model(value, target_type)

            # Get the origin type (for generics like List, Dict, etc.)
            origin = get_origin(target_type)
            args = get_args(target_type)

            # Handle dictionary types - raise UnsupportedParameterException
            if origin in (dict, Dict):
                param_type = str(target_type)
                raise UnsupportedParameterException(param_name, param_type)

            # Handle sequence types (lists and tuples) consistently
            if origin in (list, tuple):
                return self._convert_to_sequence(value, origin, args)

            # For primitive types, try direct conversion
            try:
                # Only attempt conversion for basic types, not for complex types
                if inspect.isclass(target_type) and not hasattr(target_type, "__origin__"):
                    return target_type(value)
            except (TypeError, ValueError):
                return "Tool call parameter type conversion failed."

            # If conversion fails or isn't applicable, return the original value
            return value

        def _convert_to_pydantic_model(self, value: Any, model_class: Type[BaseModel]) -> Any:
            """Convert a value to a Pydantic model."""
            if isinstance(value, dict):
                return model_class(**value)
            elif hasattr(value, "__dict__"):
                return model_class(**value.__dict__)
            return value

        def _convert_to_sequence(
            self, value: Any, target_type: Type, type_args: Tuple[Type, ...]
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
                result = [self._convert_element(item, type_args, i) for i, item in enumerate(value)]
                # Return as the target type (list or tuple)
                return tuple(result) if target_type is tuple else result

            # For any non-sequence type, wrap in a sequence with a single element
            result = [self._convert_element(value, type_args, 0)]
            return tuple(result) if target_type is tuple else result

        def _convert_element(self, value: Any, type_args: Tuple[Type, ...], index: int) -> Any:
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
            return self._convert_value(value, element_type)

        def pretty_name(self) -> str:
            return f"{func.__name__} Node"

        @classmethod
        def tool_info(cls) -> Tool:
            return Tool.from_function(func)

        @classmethod
        def prepare_tool(cls, tool_parameters: Dict[str, Any]) -> Self:
            return cls(**tool_parameters)

    return DynamicFunctionNode


class FunctionNode(Node[_TOutput]):
    """
    A class for ease of creating a function node for the user
    """

    def __init__(self, func: Callable[..., _TOutput], **kwargs: dict[str, Any]):
        super().__init__()
        self.func = func
        self.kwargs = kwargs

    def invoke(self) -> _TOutput:
        try:
            result = self.func(**self.kwargs)
            if result and isinstance(result, str):
                self.data_streamer(result)

            return result
        except Exception as e:
            raise RuntimeError(f"Error invoking function: {str(e)}")

    def pretty_name(self) -> str:
        return f"Function Node - {self.__class__.__name__}({self.func.__name__})"

    def tool_info(self) -> Tool:
        return self.func

    @classmethod
    def prepare_tool(cls, tool_parameters):
        return cls(**tool_parameters)
