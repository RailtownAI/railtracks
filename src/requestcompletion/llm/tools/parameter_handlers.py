"""
Parameter type handlers.

This module contains handler classes for different parameter types using the strategy pattern.
Each handler is responsible for determining if it can handle a specific parameter type
and creating the appropriate Parameter object.
"""

import inspect
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Tuple

from pydantic import BaseModel

from .parameter import Parameter, PydanticParameter
from .schema_parser import parse_model_properties


class ParameterHandler(ABC):
    """Base abstract class for parameter handlers."""

    @abstractmethod
    def can_handle(self, param_annotation: Any) -> bool:
        """
        Determines if this handler can process the given parameter annotation.

        Args:
            param_annotation: The parameter annotation to check.

        Returns:
            True if this handler can process the annotation, False otherwise.
        """
        pass

    @abstractmethod
    def create_parameter(
        self, param_name: str, param_annotation: Any, description: str, required: bool
    ) -> Parameter:
        """
        Creates a Parameter object for the given parameter.

        Args:
            param_name: The name of the parameter.
            param_annotation: The parameter's type annotation.
            description: The parameter's description.
            required: Whether the parameter is required.

        Returns:
            A Parameter object representing the parameter.
        """
        pass


class PydanticModelHandler(ParameterHandler):
    """Handler for Pydantic model parameters."""

    def can_handle(self, param_annotation: Any) -> bool:
        """Check if the annotation is a Pydantic model."""
        return inspect.isclass(param_annotation) and issubclass(
            param_annotation, BaseModel
        )

    def create_parameter(
        self, param_name: str, param_annotation: Any, description: str, required: bool
    ) -> Parameter:
        """Create a PydanticParameter for a Pydantic model."""
        # Get the JSON schema for the Pydantic model
        schema = param_annotation.model_json_schema()

        # Process the schema to extract parameter information
        inner_params = parse_model_properties(schema)

        # Create a PydanticParameter with the extracted information
        return PydanticParameter(
            name=param_name,
            param_type="object",
            description=description,
            required=required,
            properties=inner_params,
        )


class SequenceParameterHandler(ParameterHandler):
    """Handler for sequence parameters (lists and tuples)."""

    def can_handle(self, param_annotation: Any) -> bool:
        """Check if the annotation is a list or tuple type."""
        # Handle typing.List and typing.Tuple
        if hasattr(param_annotation, "__origin__"):
            return param_annotation.__origin__ in (list, tuple)

        # Handle direct list and tuple types
        return param_annotation in (list, tuple, List, Tuple)

    def create_parameter(
        self, param_name: str, param_annotation: Any, description: str, required: bool
    ) -> Parameter:
        """Create a Parameter for a list or tuple."""
        # Determine if it's a list or tuple
        is_tuple = False
        if hasattr(param_annotation, "__origin__"):
            is_tuple = param_annotation.__origin__ is tuple
        else:
            is_tuple = param_annotation in (tuple, Tuple)

        sequence_type = "tuple" if is_tuple else "list"

        # Get the element types if available
        sequence_args = []
        if hasattr(param_annotation, "__args__"):
            sequence_args = getattr(param_annotation, "__args__", [])

        # For tuples, we have multiple types (potentially)
        if is_tuple:
            type_names = [
                t.__name__ if hasattr(t, "__name__") else str(t) for t in sequence_args
            ]
            type_desc = (
                f"{sequence_type} of {', '.join(type_names)}"
                if type_names
                else sequence_type
            )
        # For lists, we have a single type
        else:
            if sequence_args:
                element_type = sequence_args[0]
                type_name = (
                    element_type.__name__
                    if hasattr(element_type, "__name__")
                    else str(element_type)
                )
                type_desc = f"{sequence_type} of {type_name}"

                # Check if the element type is a Pydantic model
                if inspect.isclass(element_type) and issubclass(
                    element_type, BaseModel
                ):
                    # Get the JSON schema for the Pydantic model
                    schema = element_type.model_json_schema()

                    # Process the schema to extract parameter information
                    inner_params = parse_model_properties(schema)

                    # Create a PydanticParameter with the extracted information
                    if description:
                        description += f" (Expected format: {type_desc})"
                    else:
                        description = f"Expected format: {type_desc}"

                    return PydanticParameter(
                        name=param_name,
                        param_type="array",
                        description=description,
                        required=required,
                        properties=inner_params,
                    )
            else:
                type_desc = sequence_type

        if description:
            description += f" (Expected format: {type_desc})"
        else:
            description = f"Expected format: {type_desc}"

        # For regular sequences, use the array type
        return Parameter(
            name=param_name,
            param_type="array",
            description=description,
            required=required,
        )

    def _get_param_type_for_annotation(self, annotation: Any) -> str:
        """Get the parameter type string for a type annotation."""
        if issubclass(annotation, int):
            return "integer"
        elif issubclass(annotation, float):
            return "float"
        elif issubclass(annotation, bool):
            return "boolean"
        else:
            return "string"  # Default to string for other types


class DictParameterHandler(ParameterHandler):
    """Handler for dictionary parameters that raises an exception."""

    def can_handle(self, param_annotation: Any) -> bool:
        """Check if the annotation is a dictionary type."""
        return hasattr(
            param_annotation, "__origin__"
        ) and param_annotation.__origin__ in (dict, Dict)

    def create_parameter(
        self, param_name: str, param_annotation: Any, description: str, required: bool
    ) -> Parameter:
        """Raise an exception for dictionary parameters."""
        # Get the key and value types if available for better error message
        dict_args = getattr(param_annotation, "__args__", [])
        key_type = dict_args[0] if len(dict_args) > 0 else "unknown"
        value_type = dict_args[1] if len(dict_args) > 1 else "unknown"

        key_type_name = (
            key_type.__name__ if hasattr(key_type, "__name__") else str(key_type)
        )
        value_type_name = (
            value_type.__name__ if hasattr(value_type, "__name__") else str(value_type)
        )

        param_type = f"Dict[{key_type_name}, {value_type_name}]"

        # Raise an exception for dictionary parameters
        raise UnsupportedParameterError(param_name, param_type)


class DefaultParameterHandler(ParameterHandler):
    """Default handler for primitive types and unknown types."""

    def __init__(self):
        """Initialize with type mapping."""
        self.type_mapping = {
            str: "string",
            int: "integer",
            float: "float",
            bool: "boolean",
            list: "array",
            List: "array",
            tuple: "array",
            Tuple: "array",
            dict: "object",
            Dict: "object",
        }

    def can_handle(self, param_annotation: Any) -> bool:
        """This handler can handle any parameter type as a fallback."""
        return True

    def create_parameter(
        self, param_name: str, param_annotation: Any, description: str, required: bool
    ) -> Parameter:
        """Create a Parameter for a primitive or unknown type."""
        # Check if it's a dictionary type that wasn't caught by DictParameterHandler
        if param_annotation in (dict, Dict):
            raise UnsupportedParameterError(param_name, str(param_annotation))

        # Default to object if type not found in mapping
        mapped_type = self.type_mapping.get(param_annotation, "object")
        return Parameter(
            name=param_name,
            param_type=mapped_type,
            description=description,
            required=required,
        )


class UnsupportedParameterError(Exception):
    """Exception raised when a parameter type is not supported."""

    def __init__(self, param_name: str, param_type: str):
        self.message = (
            f"Unsupported parameter type: {param_type} for parameter: {param_name}"
        )
        super().__init__(self.message)
