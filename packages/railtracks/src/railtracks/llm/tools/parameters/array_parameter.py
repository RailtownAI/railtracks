from typing import Any, Dict, Optional, List
from ._base import Parameter, ParameterType

class ArrayParameter(Parameter):
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
        super().__init__(name, description, required, default)
        self.items = items
        self.max_items = max_items
        self.additional_properties = additional_properties  # might be relevant if items is object type

    def to_json_schema(self) -> Dict[str, Any]:
        schema: Dict[str, Any] = {
            "type": self.param_type.value,
            "items": self.items.to_json_schema(),
        }

        if self.description:
            schema["description"] = self.description
        if self.max_items is not None:
            schema["maxItems"] = self.max_items
        if self.additional_properties:
            # Only applicable if items is object-like, but we add for completeness
            schema["additionalProperties"] = self.additional_properties

        if self.default is not None:
            schema["default"] = self.default

        return schema

    @classmethod
    def from_json_schema(cls, name: str, schema: dict, required: bool) -> "ArrayParameter":
        items_schema = schema.get("items", {"type": "string"})
        from ._base import Parameter  # avoid circular import

        items_param = Parameter.factory(name + "_item", items_schema, True)
        description = schema.get("description")
        default = schema.get("default")
        max_items = schema.get("maxItems")
        additional_properties = schema.get("additionalProperties", False)

        return cls(
            name=name,
            items=items_param,
            description=description,
            required=required,
            default=default,
            max_items=max_items,
            additional_properties=additional_properties,
        )

    def __repr__(self) -> str:
        return (
            f"ArrayParameter(name={self.name!r}, items={self.items!r}, "
            f"description={self.description!r}, required={self.required!r}, "
            f"default={self.default!r}, max_items={self.max_items!r}, "
            f"additional_properties={self.additional_properties!r})"
        )