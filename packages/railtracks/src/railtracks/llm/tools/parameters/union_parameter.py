from typing import List, Optional, Dict, Any
from .default_parameter import DefaultParameter
from ._base import Parameter

class UnionParameter(Parameter):
    param_type: List[str]

    def __init__(
        self,
        name: str,
        options: List[DefaultParameter],
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


    def __repr__(self) -> str:
        return (
            f"UnionParameter(name={self.name!r}, options={self.options!r}, "
            f"description={self.description!r}, required={self.required!r}, default={self.default!r})"
        )