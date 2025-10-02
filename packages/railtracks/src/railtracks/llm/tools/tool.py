"""
Tool class for representing function-based tools.

This module contains the Tool class which represents a callable tool with
parameters and descriptions.
"""

import inspect
import warnings
from typing import Any, Callable, Dict, Iterable, List, Type

from pydantic import BaseModel
from typing_extensions import Self

from .._exception_base import RTLLMError
from .docstring_parser import extract_main_description, parse_docstring_args
from .parameter_handlers import (
    DefaultParameterHandler,
    ParameterHandler,
    PydanticModelHandler,
    SequenceParameterHandler,
    UnionParameterHandler,
)
from .parameters import Parameter
from .schema_parser import parse_json_schema_to_parameter


class Tool:
    """
    A quasi-immutable class designed to represent a single Tool object.
    You pass in key details (name, description, and required parameters).
    """

    def __init__(
        self,
        name: str,
        detail: str,
        parameters: Iterable[Parameter] | Dict[str, Any] | None = None,
    ):
        """
        Creates a new Tool instance.

        Args:
            name: The name of the tool.
            detail: A detailed description of the tool.
            parameters: Parameters attached to this tool; a set of Parameter objects, or a dict.
        """

        if (
            isinstance(parameters, dict) and len(parameters) > 0
        ):  # if parameters is a JSON-output_schema, convert into Parameter objects (Checks should be done in validate_tool_params)
            props = parameters.get("properties")
            required_fields = list(parameters.get("required", []))
            param_objs: List[Parameter] = []
            for name, prop in props.items():
                param_objs.append(
                    parse_json_schema_to_parameter(name, prop, name in required_fields)
                )
            parameters = param_objs

        self._name = name
        self._detail = detail
        self._parameters = parameters

    @property
    def name(self) -> str:
        """Get the name of the tool."""
        return self._name

    @property
    def detail(self) -> str:
        """Returns the detailed description for this tool."""
        return self._detail

    @property
    def parameters(self) -> List[Parameter] | None:
        """Gets the parameters attached to this tool (if any)."""
        return self._parameters

    def __str__(self) -> str:
        """String representation of the tool."""
        if self._parameters:
            params_str = "{" + ", ".join(str(p) for p in self._parameters) + "}"
        return f"Tool(name={self._name}, detail={self._detail}, parameters={params_str if self._parameters else 'None'})"

    @classmethod
    def from_function(
        cls,
        func: Callable,
        /,
        *,
        name: str | None = None,
        details: str | None = None,
        params: Type[BaseModel] | Dict[str, Any] | List[Parameter] | None = None,
    ) -> Self:
        """
        Creates a Tool from a Python callable.
        Uses the function's docstring and type annotations to extract details and parameter info.

        KEY NOTE: No checking is done to ensure that the inserted params match the function signature

        Args:
            func: The function to create a tool from.
            name: Optional name for the tool. If not provided, uses the function's name.
            details: Optional detailed description for the tool. If not provided, extracts from the function's docstring.
            params: Optional parameters for the tool. If not provided, infers from the function's signature and docstring.

        Returns:
            A Tool instance representing the function.
        """
        # TODO: add set verification to ensure that the params match the function signature
        # Check if the function is a method in a class
        in_class = bool(func.__qualname__ and "." in func.__qualname__)

        # Parse the docstring to get parameter descriptions
        arg_descriptions = parse_docstring_args(func.__doc__ or "")

        try:
            # Get the function signature
            signature = inspect.signature(func)
        except ValueError:
            raise ToolCreationError(
                message="Cannot convert kwargs for builtin functions.",
                notes=[
                    "Please use a cutom made function.",
                    "Eg.- \ndef my_custom_function(a: int, b: str):\n    pass",
                ],
            )

        if name is not None:
            # TODO: add some checking here to ensure that the name is valid snake case.
            function_name = name
        else:
            function_name = func.__name__

        docstring = func.__doc__.strip() if func.__doc__ else ""

        if params is not None:
            parameters = params
        else:
            # Check for multiple Args sections (warning)
            # Only need to do this if we need to.
            if docstring.count("Args:") > 1:
                warnings.warn("Multiple 'Args:' sections found in the docstring.")
            # Create parameter handlers
            handlers: List[ParameterHandler] = [
                PydanticModelHandler(),
                SequenceParameterHandler(),
                UnionParameterHandler(),
                DefaultParameterHandler(),
            ]

            parameters: List[Parameter] = []

            for param in signature.parameters.values():
                # Skip 'self' parameter for class methods
                if in_class and (param.name == "self" or param.name == "cls"):
                    continue

                description = arg_descriptions.get(param.name, "")

                # Check if the parameter is required
                required = param.default == inspect.Parameter.empty

                handler = next(h for h in handlers if h.can_handle(param.annotation))

                param_obj = handler.create_parameter(
                    param.name, param.annotation, description, required
                )

                parameters.append(param_obj)

        if details is not None:
            main_description = details
        else:
            main_description = extract_main_description(docstring)

        tool_info = Tool(
            name=function_name,
            detail=main_description,
            parameters=parameters,
        )
        return tool_info

    @classmethod
    def from_mcp(cls, tool) -> Self:
        """
        Creates a Tool from an MCP tool object.

        Args:
            tool: The MCP tool to create a Tool from.

        Returns:
            A Tool instance representing the MCP tool.
        """
        input_schema = getattr(tool, "inputSchema", None)
        if not input_schema or input_schema["type"] != "object":
            raise ToolCreationError(
                message="The inputSchema for an MCP Tool must be 'object'. ",
                notes=[
                    "If an MCP tool has a different output_schema, create a GitHub issue and support will be added."
                ],
            )

        properties = input_schema.get("properties", {})
        required_fields = set(input_schema.get("required", []))
        param_objs = set()
        for name, prop in properties.items():
            required = name in required_fields
            param_objs.add(parse_json_schema_to_parameter(name, prop, required))

        return cls(name=tool.name, detail=tool.description, parameters=param_objs)


class ToolCreationError(RTLLMError):
    """Exception raised when a tool cannot be created."""

    def __init__(self, message, notes=None):
        super().__init__(message)
        self.notes = notes or []

    def __str__(self):
        base = super().__str__()
        if self.notes:
            notes_str = (
                "\n"
                + self._color("Tips to debug:\n", self.GREEN)
                + "\n".join(self._color(f"- {note}", self.GREEN) for note in self.notes)
            )
            return f"\n{self._color(base, self.RED)}{notes_str}"
        return self._color(base, self.RED)
