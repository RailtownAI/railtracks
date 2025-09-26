from typing import Any, Dict, Optional

from ._base import Parameter, ParameterType


class ObjectParameter(Parameter):
    param_type: ParameterType = ParameterType.OBJECT

    def __init__(
        self,
        name: str,
        properties: list[Parameter],
        description: Optional[str] = None,
        required: bool = True,
        additional_properties: bool = False,
        default: Any = None,
    ):
        super().__init__(name, description, required, default)
        self.properties = properties
        self.additional_properties = additional_properties

    def to_json_schema(self) -> Dict[str, Any]:
        schema = {
            "type": "object",
            "properties": {},
            "additionalProperties": self.additional_properties,
        }

        if self.description:
            schema["description"] = self.description

        required_props = []
        for prop in self.properties:
            schema["properties"][prop.name] = prop.to_json_schema()
            if prop.required:
                required_props.append(prop.name)

        if required_props:
            schema["required"] = required_props

        if self.default is not None:
            schema["default"] = self.default

        if self.enum:
            schema["enum"] = self.enum

        return schema

    def __repr__(self) -> str:
        return (
            f"ObjectParameter(name={self.name!r}, properties={self.properties!r}, "
            f"description={self.description!r}, required={self.required!r}, "
            f"additional_properties={self.additional_properties!r}, default={self.default!r})"
        )
