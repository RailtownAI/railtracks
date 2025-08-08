import inspect
from typing import Any, Callable, Dict, List, Tuple, Type, Union, get_args, get_origin

from pydantic import BaseModel


class TypeMapper:
    """
    A simple type that will provide functionality to convert a dictionary representation of kwargs into the appropriate
    types based on the function signature

    Use the method `convert_kwargs_to_appropriate_types` to convert the kwargs dictionary.
    """

    def __init__(self, function: Callable):
        try:
            self.sig = inspect.signature(function)
        except ValueError:
            raise RuntimeError(
                "Cannot convert kwargs for builtin functions. "
                "Please use a custom function."
            )

    def convert_kwargs_to_appropriate_types(self, kwargs) -> Dict[str, Any]:
        """Convert kwargs to appropriate types based on function signature."""
        converted_kwargs = {}

        sig = self.sig

        # Process all parameters from the function signature
        for param_name, param in sig.parameters.items():
            # If the parameter is in kwargs, convert it
            if param_name in kwargs:
                converted_kwargs[param_name] = self._convert_value(
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
            raise RuntimeError(param_name, param_type)

        # Handle sequence types (lists and tuples) consistently
        if origin in (list, tuple):
            return cls._convert_to_sequence(value, origin, args)

        # For primitive types, try direct conversion
        try:
            # Only attempt conversion for basic types, not for complex types
            if inspect.isclass(target_type) and not hasattr(target_type, "__origin__"):
                return target_type(value)
        except (TypeError, ValueError):
            return value

        # If conversion fails or isn't applicable, return the original value
        return value

    @classmethod
    def _convert_to_pydantic_model(
        cls, value: Any, model_class: Type[BaseModel]
    ) -> Any:
        """Convert a value to a Pydantic model."""
        if isinstance(value, dict):
            return model_class(**value)
        raise RuntimeError(str(value), str(type(value)))

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
                cls._convert_element(item, type_args, i) for i, item in enumerate(value)
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
