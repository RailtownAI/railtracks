"""Parameter class for array types."""

from typing import Any, Dict, Optional

from ._base import Parameter, ParameterType


class ArrayParameter(Parameter):
    """Parameter representing an array type."""

    param_type: ParameterType = ParameterType.ARRAY

    def __init__(
        self,
        name: str,
        items: Parameter,
        description: Optional[str] = None,
        required: bool = True,
        default: Any = None,
        max_items: Optional[int] = None,
        additional_properties: bool = False,
    ):
        """Initialize an ArrayParameter instance.

        Args:
            name (str): Name of the parameter.
            items (Parameter): Parameter instance describing the type of array elements.
            description (Optional[str]): Description of the parameter.
            required (bool): Whether the parameter is required.
            default (Any): Default value for the parameter.
            max_items (Optional[int]): Maximum number of items allowed in the array.
            additional_properties (bool): Whether additional properties are allowed (relevant if items are objects).
        """
        super().__init__(name, description, required, default)
        self.items = items
        self.max_items = max_items
        self.additional_properties = (
            additional_properties  # might be relevant if items is object type
        )

    def to_json_schema(self) -> Dict[str, Any]:
        """Convert the array parameter to a JSON schema representation."""
        # Base property for items inside the array
        items_schema = self.items.to_json_schema()

        schema = {
            "type": "array",
            "items": items_schema,
        }
        if self.description:
            schema["description"] = self.description

        if self.max_items is not None:
            schema["maxItems"] = self.max_items

        # Set defaults and enum if present at the array level
        if self.default is not None:
            schema["default"] = self.default

        # Note: enum on arrays is uncommon but if you want to support:
        if self.enum:
            schema["enum"] = self.enum

        return schema

    def __repr__(self) -> str:
        """Return a string representation of the ArrayParameter."""
        return (
            f"ArrayParameter(name={self.name!r}, items={self.items!r}, "
            f"description={self.description!r}, required={self.required!r}, "
            f"default={self.default!r}, max_items={self.max_items!r}, "
            f"additional_properties={self.additional_properties!r})"
        )
