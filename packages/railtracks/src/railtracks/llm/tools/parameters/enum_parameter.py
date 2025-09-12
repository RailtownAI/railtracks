from typing import List, Optional, Dict, Any
from ._base import Parameter

class EnumParameter(Parameter):
    param_type: str = "enum"  # enum is a special case (often type + enum), but we'll identify by presence of enum

    def __init__(
        self,
        name: str,
        enum_values: List[Any],
        description: Optional[str] = None,
        required: bool = True,
        default: Any = None,
    ):
        super().__init__(name, description, required, default, enum=enum_values)
        self.enum_values = enum_values

    def to_json_schema(self) -> Dict[str, Any]:
        schema = {}
        if self.enum_values:
            schema["enum"] = self.enum_values
        if self.description:
            schema["description"] = self.description
        # Enums typically have a type; infer from first enum item if possible
        if self.enum_values:
            first_value = self.enum_values[0]
            from ._base import ParameterType
            try:
                schema["type"] = ParameterType.from_python_type(type(first_value)).value
            except Exception:
                schema["type"] = "string"
        if self.default is not None:
            schema["default"] = self.default
        return schema

    @classmethod
    def from_json_schema(cls, name: str, schema: dict, required: bool) -> "EnumParameter":
        enum_values = schema.get("enum", [])
        description = schema.get("description")
        default = schema.get("default")
        return cls(
            name=name,
            enum_values=enum_values,
            description=description,
            required=required,
            default=default,
        )

    def __repr__(self) -> str:
        return (
            f"EnumParameter(name={self.name!r}, enum_values={self.enum_values!r}, "
            f"description={self.description!r}, required={self.required!r}, default={self.default!r})"
        )