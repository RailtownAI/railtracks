"""Parameter class for union types."""

from typing import Any, Dict, List, Optional

from ._base import Parameter


class UnionParameter(Parameter):
    """Parameter representing a union type."""

    param_type: List[str]

    def __init__(
        self,
        name: str,
        options: List[Parameter],
        description: Optional[str] = None,
        required: bool = True,
        default: Any = None,
        enum: Optional[list] = None,
        default_present: bool = False,
    ):
        """Initialize a UnionParameter instance.

        Args:
            name (str): Name of the parameter.
            options (List[Parameter]): List of Parameter instances representing the union types.
            description (Optional[str]): Description of the parameter.
            required (bool): Whether the parameter is required.
            default (Any): Default value for the parameter.
            enum (Optional[list]): Allowed values for the parameter.
            default_present (bool): Whether a default value is explicitly set.
        """
        super().__init__(name, description, required, default, enum, default_present)
        self.options = options
        for opt in options:
            if isinstance(opt, UnionParameter):
                raise TypeError(
                    "UnionParameter cannot contain another UnionParameter in its options"
                )

        # param_type here is the list of inner types as strings, e.g. ["string", "null"]
        # flatten and deduplicate types (order does not matter for schema)
        flattened_types = []
        for opt in options:
            pt = opt.param_type
            if hasattr(pt, "value"):
                pt = pt.__getattribute__("value")
            if isinstance(pt, list):
                flattened_types.extend(p for p in pt if p is not None)
            elif pt is not None:
                flattened_types.append(pt)

        # Deduplicate while preserving order
        self.param_type = list(set(flattened_types))

    def to_json_schema(self) -> Dict[str, Any]:
        """Convert the union parameter to a JSON schema representation."""
        schema = {
            "anyOf": [opt.to_json_schema() for opt in self.options],
        }

        if self.description:
            schema["description"] = self.description  # type: ignore

        if self.default_present:
            schema["default"] = self.default

        return schema

    def __repr__(self) -> str:
        """Return a string representation of the UnionParameter."""
        return (
            f"UnionParameter(name={self.name!r}, options={self.options!r}, "
            f"description={self.description!r}, required={self.required!r}, default={self.default!r})"
        )
