"""
Parameter classes for tool parameter definitions.

This module contains the base Parameter class and its extensions for representing
tool parameters with various type information and nested structures.
"""

from copy import deepcopy
from enum import Enum
from typing import Any, Dict, Literal, Optional


class ParameterType(str, Enum):
    """Enum representing the possible parameter types for tool parameters."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


class Parameter:
    """Base class for representing a tool parameter."""

    def __init__(
        self,
        name: str,
        param_type: Literal["string", "integer", "float", "boolean", "array", "object"],
        description: str = "",
        required: bool = True,
        additional_properties: bool = False,
    ):
        """
        Creates a new instance of a parameter object.

        Args:
            name: The name of the parameter.
            param_type: The type of the parameter.
            description: A description of the parameter.
            required: Whether the parameter is required. Defaults to True.
            additional_properties: Whether to allow additional properties for object types. Defaults to False.
        """
        self._name = name
        self._param_type = param_type
        self._description = description
        self._required = required
        self._additional_properties = additional_properties

    @property
    def name(self) -> str:
        """Get the name of the parameter."""
        return self._name

    @property
    def param_type(self) -> str:
        """Get the type of the parameter."""
        return self._param_type

    @property
    def description(self) -> str:
        """Get the description of the parameter."""
        return self._description

    @property
    def required(self) -> bool:
        """Check if the parameter is required."""
        return self._required

    @property
    def additional_properties(self) -> bool:
        """Check if additional properties are allowed for object types."""
        return self._additional_properties

    def __str__(self) -> str:
        """String representation of the parameter."""
        return (
            f"Parameter(name={self._name}, type={self._param_type}, "
            f"description={self._description}, required={self._required}, "
            f"additional_properties={self._additional_properties})"
        )

    @classmethod
    def type_mapping(cls) -> Dict[str, Any]:
        """Map parameter types to Python types."""
        return deepcopy(
            {
                "string": str,
                "integer": int,
                "float": float,
                "boolean": bool,
                "array": list,
                "object": dict,
            }
        )


class PydanticParameter(Parameter):
    """Extended Parameter class that can represent nested object structures."""

    def __init__(
        self,
        name: str,
        param_type: Literal["string", "integer", "float", "boolean", "array", "object"],
        description: str = "",
        required: bool = True,
        properties: Optional[Dict[str, Parameter]] = None,
        additional_properties: bool = False,
    ):
        """
        Creates a new instance of a PydanticParameter object.

        Args:
            name: The name of the parameter.
            param_type: The type of the parameter.
            description: A description of the parameter.
            required: Whether the parameter is required. Defaults to True.
            properties: Nested properties if this parameter is itself an object.
            additional_properties: Whether to allow additional properties for object types. Defaults to False.
        """
        super().__init__(name, param_type, description, required, additional_properties)
        self._properties = properties or {}

    @property
    def properties(self) -> Dict[str, Parameter]:
        """Get the nested properties of this parameter."""
        return self._properties

    def __str__(self) -> str:
        return (
            f"PydanticParameter(name={self._name}, type={self._param_type}, "
            f"description={self._description}, required={self._required}, "
            f"additional_properties={self._additional_properties}, properties={self._properties})"
        )
