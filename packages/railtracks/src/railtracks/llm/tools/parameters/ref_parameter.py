from typing import Any, Dict, Optional

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
        schema = {"$ref": self.ref_path}
        if self.description:
            schema["description"] = self.description

        if self.default is not None:
            schema["default"] = self.default

        if self.enum:
            schema["enum"] = self.enum

        return schema

    def __repr__(self) -> str:
        return (
            f"RefParameter(name={self.name!r}, ref_path={self.ref_path!r}, "
            f"description={self.description!r}, required={self.required!r}, default={self.default!r})"
        )
