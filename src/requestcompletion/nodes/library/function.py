from __future__ import annotations

import inspect
import re

from typing import (
    Any,
    TypeVar,
    Callable,
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

    def _tool_info_from_func(self, func: Callable):

        # determine if it's a class method
        in_class = bool(func.__qualname__ and "." in func.__qualname__)

        arg_descriptions = self._parse_docstring_args(func.__doc__)

        signature = inspect.signature(func)
        
        parameters = []
        for param in signature.parameters.values():
            parameters.append(Parameter(
                name=param.name,
                param_type=param.annotation,
                description=arg_descriptions.get(param.name, ""),
                required=param.default == inspect.Parameter.empty
            ))

        tool_info = Tool(
            name=func.__name__,
            detail=func.__doc__,
            parameters=parameters,
        )
        
        return tool_info
    
    def _parse_docstring_args(docstring: str) -> dict[str, str]:
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
                # Everything after the "Args:" line is assumed to be part of the parameters section.
                args_section = "\n".join(split_lines[i+1:])
                break

        # Use regex to capture lines of the form "name (type): description"
        # This regex assumes each argument is on a separate line.
        # You may need to tweak it for multi-line descriptions.
        pattern = re.compile(r'^\s*(\w+)\s*\([^)]+\):\s*(.+)$')

        arg_descriptions = {}
        for line in args_section.splitlines():
            match = pattern.match(line)
            if match:
                arg_name, arg_desc = match.groups()
                arg_descriptions[arg_name] = arg_desc.strip()

        return arg_descriptions
