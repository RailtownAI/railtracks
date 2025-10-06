from abc import ABC
from enum import Enum
from typing import Any, Dict, List, Optional, TypeVar, Union


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
            "none": cls.NONE,  # in case of recieving a list of string (type = ["object", "none"])
        }
        return mapping.get(py_type, cls.OBJECT)


# Generic Type for subclass methods that return Parameter
T = TypeVar("T", bound="Parameter")


class Parameter(ABC):
    """
    Abstract Base Parameter class with default simple parameter behavior.
    """

    param_type: Optional[Union[str, List[str]]] = None  # class var for default type

    def __init__(
        self,
        name: str,
        description: Optional[str] = None,
        required: bool = True,
        default: Any = None,
        enum: Optional[List[Any]] = None,
        default_present: bool = False,
        param_type: Optional[Union[str, List[str]]] = None,
    ):
        """
        Initialize a Parameter instance.

        Args:
            name (str): Name of the parameter.
            description (Optional[str]): Description of the parameter.
            required (bool): Whether the parameter is required.
            default (Any): Default value for the parameter.
            enum (Optional[List[Any]]): Allowed values for the parameter.
            default_present (bool): Whether a default value is explicitly set.
            param_type (Optional[Union[str, List[str]]]): The type or types of the parameter.
        """
        self.name = name
        self.description = description or ""
        self.required = required
        self.default = default
        self.enum = enum
        self.default_present = default_present
        if param_type is not None:
            # Accept either list[str], str, or ParameterType enum or list of them
            # Normalize to str or List[str]
            if isinstance(param_type, list):
                self.param_type = [
                    pt.value if isinstance(pt, ParameterType) else pt
                    for pt in param_type
                ]
            else:
                self.param_type = (
                    param_type.value
                    if isinstance(param_type, ParameterType)
                    else param_type
                )
        elif hasattr(self, "param_type") and self.param_type is None:
            self.param_type = None

    def to_json_schema(self) -> Dict[str, Any]:
        # Base dictionary with type and optional description
        schema_dict: Dict[str, Any] = {
            "type": self.param_type.value
            if isinstance(self.param_type, ParameterType)
            else self.param_type
        }
        if self.description:
            schema_dict["description"] = self.description

        # Handle enum
        if self.enum:
            schema_dict["enum"] = self.enum

        # Handle default
        # default can be None, 0, False; None means optional parameter
        if self.default_present:
            schema_dict["default"] = self.default
        elif isinstance(self.param_type, list) and "none" in self.param_type:
            schema_dict["default"] = None

        return schema_dict

    def __repr__(self) -> str:
        return (
            f"Parameter(name={self.name!r}, param_type={self.param_type!r}, "
            f"description={self.description!r}, required={self.required!r}, "
            f"default={self.default!r}, enum={self.enum!r})"
        )
