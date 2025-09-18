from enum import Enum
from typing import Any, List, Union, Optional, Dict, Type, Literal, ClassVar, TypeVar
from abc import ABC, abstractmethod

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

# Generic Type for subclass methods that return Parameter
T = TypeVar("T", bound="Parameter")

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


    def __repr__(self):
        cls_name = self.__class__.__name__
        return (
            f"{cls_name}(name={self.name!r}, description={self.description!r}, "
            f"required={self.required!r}, default={self.default!r}, enum={self.enum!r})"
        )