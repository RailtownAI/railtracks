from typing import List, Optional, Dict, Any
from ._base import Parameter

class UnionParameter(Parameter):
    param_type: List[str]

    def __init__(
        self,
        name: str,
        options: List[Parameter],
        description: Optional[str] = None,
        required: bool = True,
        default: Any = None,
    ):
        super().__init__(name, description, required, default)
        self.options = options
        for opt in options:
            if isinstance(opt, UnionParameter):
                raise TypeError("UnionParameter cannot contain another UnionParameter in its options")
        
        # param_type here is the list of inner types as strings, e.g. ["string", "null"]  
        self.param_type = [opt.param_type if hasattr(opt.param_type, 'value') else opt.param_type for opt in options]

    def to_json_schema(self) -> Dict[str, Any]:
        return {
            "anyOf": [opt.to_json_schema() for opt in self.options],
            "description": self.description,
        }

    @classmethod
    def from_json_schema(cls, name: str, schema: dict, required: bool) -> "UnionParameter":
        anyof_key = "anyOf" if "anyOf" in schema else "oneOf"
        options_schema = schema.get(anyof_key, [])
        from ._base import Parameter

        options = []
        for i, opt_schema in enumerate(options_schema):
            opt_name = f"{name}_option_{i}"
            options.append(Parameter.factory(opt_name, opt_schema, True))

        description = schema.get("description")
        default = schema.get("default")

        return cls(
            name=name,
            options=options,
            description=description,
            required=required,
            default=default,
        )

    def __repr__(self) -> str:
        return (
            f"UnionParameter(name={self.name!r}, options={self.options!r}, "
            f"description={self.description!r}, required={self.required!r}, default={self.default!r})"
        )