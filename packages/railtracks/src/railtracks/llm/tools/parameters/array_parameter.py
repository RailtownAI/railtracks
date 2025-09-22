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
        return (
            f"ArrayParameter(name={self.name!r}, items={self.items!r}, "
            f"description={self.description!r}, required={self.required!r}, "
            f"default={self.default!r}, max_items={self.max_items!r}, "
            f"additional_properties={self.additional_properties!r})"
        )