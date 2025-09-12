"""
Parameter classes for tool parameter definitions.

This module contains the base Parameter class and its extensions for representing
tool parameters with various type information and nested structures.
"""

from .ref_parameter import RefParameter
from .default_parameter import DefaultParameter
from .object_parameter import ObjectParameter
from .array_parameter import ArrayParameter
from .enum_parameter import EnumParameter
from .union_parameter import UnionParameter

from enum import Enum
from typing import Any, List, Union, Optional, Dict, Type, Literal, ClassVar, TypeVar
from abc import ABC, abstractmethod

# Redefine ParameterType enum (you could keep your original if preferred)
class ParameterType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    NONE = "null"

    @classmethod
    def from_python_type(cls, py_type: type) -> "ParameterType":
        mapping = {
            str: cls.STRING,
            int: cls.INTEGER,
            float: cls.FLOAT,
            bool: cls.BOOLEAN,
            list: cls.ARRAY,
            tuple: cls.ARRAY,
            set: cls.ARRAY,
            dict: cls.OBJECT,
            type(None): cls.NONE,
        }
        return mapping.get(py_type, cls.OBJECT)

class Parameter(ABC):
    """
    Abstract Base Parameter class.
    """

    # The parameter type(s) that subclass represents; override in subclass
    param_type: ClassVar[Union[str, List[str], None]] = None

    def __init__(
        self,
        name: str,
        description: Optional[str] = None,
        required: bool = True,
        default: Any = None,
        enum: Optional[List[Any]] = None,
    ):
        self.name = name
        self.description = description or ""
        self.required = required
        self.default = default
        self.enum = enum

    @abstractmethod
    def to_json_schema(self) -> Dict[str, Any]:
        """
        Convert the Parameter instance back to a JSON Schema dict.
        Subclasses must implement this.
        """
        pass

    @classmethod
    @abstractmethod
    def from_json_schema(cls, name: str, schema: dict, required: bool) -> "Parameter":
        """
        Create a Parameter subclass instance from a JSON schema dict.
        Subclasses must implement this.
        """
        pass

    @classmethod
    def factory(cls, name: str, schema: dict, required: bool) -> "Parameter":
        """
        Factory method to select an appropriate subclass to parse the schema.
        """
        # Dispatch logic will be later moved or extended.
        if "$ref" in schema:
            return RefParameter.from_json_schema(name, schema, required)

        if "anyOf" in schema or "oneOf" in schema:
            return UnionParameter.from_json_schema(name, schema, required)

        if "enum" in schema:
            return EnumParameter.from_json_schema(name, schema, required)

        schema_type = schema.get("type")
        if schema_type == ParameterType.ARRAY.value:
            return ArrayParameter.from_json_schema(name, schema, required)

        if schema_type == ParameterType.OBJECT.value:
            return ObjectParameter.from_json_schema(name, schema, required)

        # fallback to default / primitive parameter
        return DefaultParameter.from_json_schema(name, schema, required)

    def __repr__(self):
        cls_name = self.__class__.__name__
        return (
            f"{cls_name}(name={self.name!r}, description={self.description!r}, "
            f"required={self.required!r}, default={self.default!r}, enum={self.enum!r})"
        )
