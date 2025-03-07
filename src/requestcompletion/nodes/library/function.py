from __future__ import annotations

import inspect
import re
import warnings

from typing import (
    Any,
    TypeVar,
    Callable,
    List,
)


from ..nodes import (
    Node,
    Tool,
    Parameter
)


TOutput = TypeVar("_TOutput")

# TODO migrate the following classes to the new system


class FunctionNode(Node[TOutput]):
    """
    A class for ease of creating a function node for the user
    """

    def __init__(self, func: Callable[..., TOutput], **kwargs: dict[str, Any]):
        super().__init__()
        self.func = func
        self.kwargs = kwargs

    def invoke(self) -> TOutput:
        try:
            result = self.func(**self.kwargs)
            if result and isinstance(result, str):
                self.data_streamer(result)

            return result
        except Exception as e:
            raise RuntimeError(f"Error invoking function: {str(e)}")

    def pretty_name(self) -> str:
        return f"Function Node - {self.__class__.__name__}({self.func.__name__})"

    def tool_info(self) -> Tool:
        return self._tool_info_from_func(self.func)

    @classmethod
    def prepare_tool(cls, tool_parameters):
        return cls(**tool_parameters)
    
    def _tool_info_from_func(self,func: Callable):

        # determine if it's a class method
        in_class = bool(func.__qualname__ and "." in func.__qualname__)

        arg_descriptions = self._parse_docstring_args(func.__doc__)

        signature = inspect.signature(func)
        
        parameters = set()
        for param in signature.parameters.values():
            if in_class and param.name == "self":
                continue
            # Map Python types to the allowed literal types
            type_mapping = {
                str: "string",
                int: "integer",
                float: "float",
                bool: "boolean",
                list: "array",
                List: "array",
            }
            
            # if inspect.isclass(param.annotation) and issubclass(param.annotation, BaseModel):
            #     schema = param.annotation.model_json_schema()
            #     parameters.append(Parameter(
            #         name=schema['title'],
            #         param_type="object",
            #         description=arg_descriptions.get(param.name, ""),
            #         required=param.default == inspect.Parameter.empty
            #     ))
            #     continue

            param_type = type_mapping.get(param.annotation, "object")

            parameters.add(Parameter(
                name=param.name,
                param_type=param_type,
                description=arg_descriptions.get(param.name, ""),
                required=param.default == inspect.Parameter.empty
            ))

        # Extract the top chunk of the docstring, excluding the 'Args:' section
        docstring = func.__doc__.strip() if func.__doc__ else ""
        if docstring.count("Args:") > 1:
            warnings.warn("Multiple 'Args:' sections found in the docstring.")
        docstring = docstring.split("Args:\n")[0].strip()

        tool_info = Tool(
            name=func.__name__,
            detail=docstring,
            parameters=parameters,
        )
        
        return tool_info
    
    def _parse_docstring_args(self, docstring: str) -> dict[str, str]:
        """
        Parses the 'Args:' section from the given docstring.
        Returns a dictionary mapping parameter names to their descriptions.
        """
        if not docstring:
            return {}

        # Look for a section starting with "Args:".
        args_section = ""
        split_lines = docstring.splitlines()
        for i, line in enumerate(split_lines):
            if line.strip().startswith("Args:"):
                # Collect lines until we hit another section or the end of the docstring
                for j in range(i + 1, len(split_lines)):
                    if re.match(r'^\s*\w+:\s*$', split_lines[j]):
                        break
                    args_section += split_lines[j] + "\n"
                break

        # Use regex to capture lines of the form "name (type): description"
        pattern = re.compile(r'^\s*(\w+)\s*\([^)]+\):\s*(.+)$')

        arg_descriptions = {}
        current_arg = None
        for line in args_section.splitlines():
            match = pattern.match(line)
            if match:
                arg_name, arg_desc = match.groups()
                arg_descriptions[arg_name] = arg_desc.strip()
                current_arg = arg_name
            elif current_arg:
                # Append to the current argument's description
                arg_descriptions[current_arg] += ' ' + line.strip()

        return arg_descriptions
