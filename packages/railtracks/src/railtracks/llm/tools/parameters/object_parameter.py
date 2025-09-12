from typing import Any, Dict, Optional, Union
from ._base import Parameter, ParameterType

class ObjectParameter(Parameter):
    param_type: ParameterType = ParameterType.OBJECT

    def __init__(
        self,
        name: str,
        properties: Dict[str, Parameter],
        description: Optional[str] = None,
        required: bool = True,
        additional_properties: bool = False,
        default: Any = None,
    ):
        super().__init__(name, description, required, default)
        self.properties = properties
        self.additional_properties = additional_properties

    def to_json_schema(self) -> Dict[str, Any]:
        schema: Dict[str, Any] = {
            "type": self.param_type.value,
            "properties": {k: v.to_json_schema() for k, v in self.properties.items()},
            "additionalProperties": self.additional_properties,
        }

        if self.description:
            schema["description"] = self.description

        required_props = [p.name for p in self.properties.values() if p.required]
        if required_props:
            schema["required"] = required_props

        if self.default is not None:
            schema["default"] = self.default

        return schema

    @classmethod
    def from_json_schema(cls, name: str, schema: dict, required: bool) -> "ObjectParameter":
        properties_schema = schema.get("properties", {})
        required_props = schema.get("required", [])
        additional_properties = schema.get("additionalProperties", False)
        from ._base import Parameter

        properties: Dict[str, Parameter] = {}

        for prop_name, prop_schema in properties_schema.items():
            prop_required = prop_name in required_props
            properties[prop_name] = Parameter.factory(prop_name, prop_schema, prop_required)

        description = schema.get("description")
        default = schema.get("default")

        return cls(
            name=name,
            properties=properties,
            description=description,
            required=required,
            additional_properties=additional_properties,
            default=default,
        )

    def __repr__(self) -> str:
        return (
            f"ObjectParameter(name={self.name!r}, properties={self.properties!r}, "
            f"description={self.description!r}, required={self.required!r}, "
            f"additional_properties={self.additional_properties!r}, default={self.default!r})"
        )