"""Parameter class for reference types."""

from typing import Any, Dict, Optional

from ._base import Parameter


class RefParameter(Parameter):
    """Parameter representing a reference type."""

    param_type: str = "object"  # referenced schemas are always 'object' type

    def __init__(
        self,
        name: str,
        ref_path: str,
        description: Optional[str] = None,
        required: bool = True,
        default: Any = None,
    ):
        """Initialize a RefParameter instance.

        Args:
            name (str): Name of the parameter.
            ref_path (str): Reference path to the schema definition.
            description (Optional[str]): Description of the parameter.
            required (bool): Whether the parameter is required.
            default (Any): Default value for the parameter.
        """
        super().__init__(name, description, required, default)
        self.ref_path = ref_path

    def to_json_schema(self) -> Dict[str, Any]:
        """Convert the reference parameter to a JSON schema representation."""
        schema = {"$ref": self.ref_path}
        if self.description:
            schema["description"] = self.description

        if self.default is not None:
            schema["default"] = self.default

        if self.enum:
            schema["enum"] = self.enum

        return schema

    def __repr__(self) -> str:
        """Return a string representation of the RefParameter."""
        return (
            f"RefParameter(name={self.name!r}, ref_path={self.ref_path!r}, "
            f"description={self.description!r}, required={self.required!r}, default={self.default!r})"
        )
