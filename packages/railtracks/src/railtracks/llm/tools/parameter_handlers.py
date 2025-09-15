"""
Parameter type handlers.

This module contains handler classes for different parameter types using the strategy pattern.
Each handler is responsible for determining if it can handle a specific parameter type
and creating the appropriate Parameter object.
"""

import inspect
import types
from abc import ABC, abstractmethod
from typing import Any, List, Tuple, Union

from pydantic import BaseModel

from .parameter import ArrayParameter, Parameter, ParameterType, PydanticParameter
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


class UnionParameterHandler(ParameterHandler):
    """Handler for Union parameters. Since Optional[x] = Union[x, None]."""

    def can_handle(self, param_annotation):
        # this is the Check for Union / Optional
        if (
            hasattr(param_annotation, "__origin__")
            and param_annotation.__origin__ is Union
        ):
            return True
        if isinstance(
            param_annotation, types.UnionType
        ):  # this handles typing.Union and the new Python 3.10+ UnionType (str | int)
            return True
        return False

    def create_parameter(
        self, param_name: str, param_annotation: Any, description: str, required: bool
    ) -> Parameter:
        """Create a Parameter for a Union parameter (including Optional)."""
        union_args = getattr(param_annotation, "__args__", [])
        param_type = []
        is_optional = False

        for t in union_args:
            if t is type(None):
                is_optional = True
            else:
                param_type.append(ParameterType.from_python_type(t).value)

        return Parameter(
            name=param_name,
            param_type=param_type,
            description=description,
            required=required and not is_optional,
        )


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
        # Get the JSON output_schema for the Pydantic model
        schema = param_annotation.model_json_schema()

        # Process the output_schema to extract parameter information
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
                    # Get the JSON output_schema for the Pydantic model
                    schema = element_type.model_json_schema()

                    # Process the output_schema to extract parameter information
                    inner_params = parse_model_properties(schema)

                    # Create a PydanticParameter with the extracted information
                    if description:
                        description += f" (Expected format: {type_desc})"
                    else:
                        description = f"Expected format: {type_desc}"

                    return ArrayParameter(
                        name=param_name,
                        param_type="object",
                        max_items=None,
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


class DefaultParameterHandler(ParameterHandler):
    """Default handler for primitive types and unknown types."""

    def can_handle(self, param_annotation: Any) -> bool:
        """This handler can handle any parameter type as a fallback."""
        return True

    def create_parameter(
        self, param_name: str, param_annotation: Any, description: str, required: bool
    ) -> Parameter:
        """Create a Parameter for a primitive or unknown type."""
        mapped_type = ParameterType.from_python_type(param_annotation).value
        return Parameter(
            name=param_name,
            param_type=mapped_type,
            description=description,
            required=required,
        )
