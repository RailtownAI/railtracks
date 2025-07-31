"""
Parameter classes for tool parameter definitions.

This module contains the base Parameter class and its extensions for representing
tool parameters with various type information and nested structures.
"""

from enum import Enum
from typing import Any, Literal, Optional


class ParameterType(str, Enum):
    """Enum representing the possible parameter types for tool parameters."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    NONE = "null"

    @classmethod
    def from_python_type(cls, py_type):
        mapping = {
            str: cls.STRING,
            int: cls.INTEGER,
            float: cls.FLOAT,
            bool: cls.BOOLEAN,
            list: cls.ARRAY,
            tuple: cls.ARRAY,
            set: cls.ARRAY,
            dict: cls.OBJECT,
        }
        return mapping.get(py_type, cls.OBJECT)


class Parameter:
    """Base class for representing a tool parameter."""

    def __init__(
        self,
        name: str,
        param_type: ParameterType
        | list[ParameterType]
        | Literal["string", "integer", "number", "boolean", "array", "object", "null"],
        description: str = "",
        required: bool = True,
        additional_properties: bool = False,
        enum: Optional[list] = None,
        default: Any = None,
    ):
        """
        Creates a new instance of a parameter object.

        Args:
            name: The name of the parameter.
            param_type: The type of the parameter.
            description: A description of the parameter.
            required: Whether the parameter is required. Defaults to True.
            additional_properties: Whether to allow additional properties for object types. Defaults to False.
            enum: The enum values for the parameter.
            default: The default value for the parameter.
        """
        # catch any input strings here.
        if isinstance(param_type, str):
            param_type = ParameterType(param_type)

        self._name = name
        self._param_type = param_type
        self._description = description
        self._required = required
        self._additional_properties = additional_properties
        self._enum = enum
        self._default = default

    @property
    def enum(self) -> Optional[list]:
        """Get the enum values for the parameter, if any."""
        return self._enum

    @property
    def default(self) -> Any:
        """Get the default value for the parameter, if any."""
        return self._default

    @property
    def name(self) -> str:
        """Get the name of the parameter."""
        return self._name

    @property
    def param_type(self) -> str | list:
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
            f"additional_properties={self._additional_properties}, "
            f"enum={self._enum}, "
            f"default={self._default})"
        )


class PydanticParameter(Parameter):
    """Extended Parameter class that can represent nested object structures."""

    def __init__(
        self,
        name: str,
        param_type: ParameterType | list[ParameterType],
        description: str = "",
        required: bool = True,
        properties: Optional[set[str, Parameter]] = None,
        additional_properties: bool = False,
        ref_path: Optional[str] = None,
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
        self._ref_path = ref_path or None

    @property
    def properties(self) -> set[str, Parameter]:
        """Get the nested properties of this parameter."""
        return self._properties

    @property
    def ref_path(self) -> Optional[str]:
        """Get the ref_path of this parameter."""
        return self._ref_path

    def __str__(self) -> str:
        return (
            f"PydanticParameter(name={self._name}, type={self._param_type}, "
            f"description={self._description}, required={self._required}, "
            f"additional_properties={self._additional_properties}, properties={self._properties}), "
            f"ref_path={self._ref_path})"
        )


class ArrayParameter(Parameter):
    """Parameter that represents an array of objects (can be nested)."""

    def __init__(
        self,
        name: str,
        param_type: ParameterType | list[ParameterType],
        max_items: int,
        description: str = "",
        required: bool = True,
        properties: Optional[set[str, Parameter]] = None,
        additional_properties: bool = False,
    ):
        super().__init__(name, param_type, description, required, additional_properties)
        self._properties = properties or {}
        self._max_items = max_items

    @property
    def properties(self) -> set[str, Parameter]:
        """Get the nested properties of this parameter."""
        return self._properties

    @property
    def max_items(self) -> int:
        """Get the maximum number of items in the array."""
        return self._max_items

    def __str__(self) -> str:
        """String representation of the parameter with properties."""
        return (
            f"ArrayParameter(name={self._name}, type={self._param_type}, "
            f"description={self._description}, required={self._required}, "
            f"additional_properties={self._additional_properties}, properties={self._properties}), "
            f"max_items={self._max_items})"
        )
