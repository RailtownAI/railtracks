from typing import Optional, Dict, Any
from ._base import Parameter

class RefParameter(Parameter):
    param_type: str = "object"  # referenced schemas are always 'object' type

    def __init__(
        self,
        name: str,
        ref_path: str,
        description: Optional[str] = None,
        required: bool = True,
        default: Any = None,
    ):
        super().__init__(name, description, required, default)
        self.ref_path = ref_path

    def to_json_schema(self) -> Dict[str, Any]:
        schema: Dict[str, Any] = {
            "$ref": self.ref_path
        }
        if self.description:
            schema["description"] = self.description
        if self.default is not None:
            schema["default"] = self.default

        return schema

    @classmethod
    def from_json_schema(cls, name: str, schema: dict, required: bool) -> "RefParameter":
        ref_path = schema.get("$ref")
        if not ref_path:
            raise ValueError(f"RefParameter must have a $ref key in schema for '{name}'")

        description = schema.get("description")
        default = schema.get("default")

        return cls(
            name=name,
            ref_path=ref_path,
            description=description,
            required=required,
            default=default,
        )

    def __repr__(self) -> str:
        return (
            f"RefParameter(name={self.name!r}, ref_path={self.ref_path!r}, "
            f"description={self.description!r}, required={self.required!r}, default={self.default!r})"
        )