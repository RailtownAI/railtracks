from typing import Any, Dict, Optional
from ._base import Parameter, ParameterType

class DefaultParameter(Parameter):
    """
    Parameter subclass for simple (primitive) JSON schema types: string, integer, number, boolean, null.
    """

    # For DefaultParameter, the param_type is a single string (one of ParameterType) or list of them.
    param_type: ParameterType  # e.g. string, integer, number etc.

    def __init__(
        self,
        name: str,
        param_type: ParameterType | str,
        description: Optional[str] = None,
        required: bool = True,
        default: Any = None,
        enum: Optional[list] = None
    ):
        # Convert strings to ParameterType if needed
        if isinstance(param_type, str):
            param_type = ParameterType(param_type)
        self.param_type = param_type
        super().__init__(name, description, required, default, enum)

    def to_json_schema(self) -> Dict[str, Any]:
        # Base dictionary with type and optional description
        schema_dict: Dict[str, Any] = {
            "type": self.param_type.value if isinstance(self.param_type, ParameterType) else self.param_type
        }
        if self.description:
            schema_dict["description"] = self.description

        # Handle enum
        if self.enum:
            schema_dict["enum"] = self.enum

        # Handle default
        # default can be None, 0, False; None means optional parameter
        if self.default is not None:
            schema_dict["default"] = self.default
        elif isinstance(self.param_type, list) and "none" in self.param_type:
            schema_dict["default"] = None

        return schema_dict

    def __repr__(self) -> str:
        return (
            f"DefaultParameter(name={self.name!r}, param_type={self.param_type!r}, "
            f"description={self.description!r}, required={self.required!r}, "
            f"default={self.default!r}, enum={self.enum!r})"
        )
