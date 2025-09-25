from typing import List, Optional, Dict, Any
from ._base import Parameter, ParameterType

class UnionParameter(Parameter):
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
        super().__init__(name, description, required, default, enum, default_present)
        self.options = options
        for opt in options:
            if isinstance(opt, UnionParameter):
                raise TypeError("UnionParameter cannot contain another UnionParameter in its options")
        
        # param_type here is the list of inner types as strings, e.g. ["string", "null"]
        # flattening incase someone tries to make UnionParameter(options=[UnionParameter(options=[...])])
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
        self.param_type = list(dict.fromkeys(flattened_types))

    def to_json_schema(self) -> Dict[str, Any]:
        schema = {
            "anyOf": [opt.to_json_schema() for opt in self.options],
        }

        if self.description:
            schema["description"] = self.description        # type: ignore

        if self.default_present:
            schema["default"] = self.default
        
        return schema


    def __repr__(self) -> str:
        return (
            f"UnionParameter(name={self.name!r}, options={self.options!r}, "
            f"description={self.description!r}, required={self.required!r}, default={self.default!r})"
        )