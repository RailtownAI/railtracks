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
        schema = {
            "type": self.param_type.value if isinstance(self.param_type, ParameterType) else self.param_type,
        }
        if self.description:
            schema["description"] = self.description

        # Set enum if present
        if self.enum:
            schema["enum"] = self.enum

        # Handle default; note: None is treated as optional and usually handled outside
        if self.default is not None:
            schema["default"] = self.default

        return schema

    @classmethod
    def from_json_schema(cls, name: str, schema: dict, required: bool) -> "DefaultParameter":
        """
        Build a DefaultParameter from JSON schema dict describing a primitive type.
        """

        # Extract type, adjusting from list type if necessary
        param_type = schema.get("type", "string")

        # If type is a list, treat as union; fallback here would be DefaultParameter only if single type
        if isinstance(param_type, list):
            # Defensive: if multiple types, DefaultParameter isn't appropriate,
            # but here choose first non-null type for fallback or treat everything as string
            filtered_types = [t for t in param_type if t != "null"]
            param_type = filtered_types[0] if filtered_types else "string"

        # Convert to ParameterType enum for consistency
        try:
            param_type_enum = ParameterType(param_type)
        except ValueError:
            # Unknown type, fallback to string
            param_type_enum = ParameterType.STRING

        description = schema.get("description")
        enum = schema.get("enum")
        default = schema.get("default")

        return cls(
            name=name,
            param_type=param_type_enum,
            description=description,
            required=required,
            default=default,
            enum=enum,
        )

    def __repr__(self) -> str:
        return (
            f"DefaultParameter(name={self.name!r}, param_type={self.param_type!r}, "
            f"description={self.description!r}, required={self.required!r}, "
            f"default={self.default!r}, enum={self.enum!r})"
        )
