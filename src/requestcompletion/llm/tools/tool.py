"""
Tool class for representing function-based tools.

This module contains the Tool class which represents a callable tool with
parameters and descriptions.
"""

import inspect
import warnings
from typing import Callable, Optional, Union, Type, Set, Dict, Any, List

from typing_extensions import Self
from pydantic import BaseModel

from .parameter import Parameter
from .schema_parser import convert_params_to_model_recursive
from .docstring_parser import parse_docstring_args, extract_main_description
from .parameter_handlers import (
    ParameterHandler,
    PydanticModelHandler,
    SequenceParameterHandler,
    DictParameterHandler,
    DefaultParameterHandler
)


class Tool:
    """
    A quasi-immutable class designed to represent a single Tool object.
    You pass in key details (name, description, and required parameters).
    """
    def __init__(
        self, 
        name: str, 
        detail: str, 
        parameters: Optional[Union[Type[BaseModel], Set[Parameter], Dict[str, Any]]] = None
    ):
        """
        Creates a new Tool instance.

        Args:
            name: The name of the tool.
            detail: A detailed description of the tool.
            parameters: Parameters attached to this tool; either a Pydantic model, a set of Parameter objects, or a dict.
        """
        # Store original parameters for debugging
        self._original_parameters = parameters if isinstance(parameters, set) else None
        
        if isinstance(parameters, set):
            self._parameters = convert_params_to_model_recursive(name, parameters)
        elif isinstance(parameters, dict):
            # If parameters is already a dict, ensure it has the required structure
            if "type" not in parameters:
                parameters["type"] = "object"
            if "additionalProperties" not in parameters:
                parameters["additionalProperties"] = False
            self._parameters = parameters
        else:
            self._parameters = parameters

        self._name = name
        self._detail = detail

    @property
    def name(self) -> str:
        """Get the name of the tool."""
        return self._name

    @property
    def detail(self) -> str:
        """Returns the detailed description for this tool."""
        return self._detail

    @property
    def parameters(self) -> Optional[Union[Type[BaseModel], Dict[str, Any]]]:
        """Gets the parameters attached to this tool (if any)."""
        return self._parameters

    def __str__(self) -> str:
        """String representation of the tool."""
        if self._parameters and hasattr(self._parameters, "model_json_schema"):
            params_schema = self._parameters.model_json_schema()
        elif isinstance(self._parameters, dict):
            params_schema = self._parameters
        else:
            params_schema = "None"
        return f"Tool(name={self._name}, detail={self._detail}, parameters={params_schema})"

    @classmethod
    def from_function(cls, func: Callable) -> Self:
        """
        Creates a Tool from a Python callable.
        Uses the function's docstring and type annotations to extract details and parameter info.
        
        Args:
            func: The function to create a tool from.
            
        Returns:
            A Tool instance representing the function.
        """
        # Check if the function is a method in a class
        in_class = bool(func.__qualname__ and "." in func.__qualname__)
        
        # Parse the docstring to get parameter descriptions
        arg_descriptions = parse_docstring_args(func.__doc__ or "")
        
        # Get the function signature
        signature = inspect.signature(func)
        
        # Create parameter handlers
        handlers: List[ParameterHandler] = [
            PydanticModelHandler(),
            SequenceParameterHandler(),
            DictParameterHandler(),
            DefaultParameterHandler()
        ]
        
        parameters: Set[Parameter] = set()
        
        for param in signature.parameters.values():
            # Skip 'self' parameter for class methods
            if in_class and param.name == "self":
                continue
            
            description = arg_descriptions.get(param.name, "")
            
            # Check if the parameter is required
            required = param.default == inspect.Parameter.empty
            
            handler = next(h for h in handlers if h.can_handle(param.annotation))
            
            param_obj = handler.create_parameter(
                param.name,
                param.annotation,
                description,
                required
            )
            
            parameters.add(param_obj)
        
        docstring = func.__doc__.strip() if func.__doc__ else ""
        main_description = extract_main_description(docstring)
        
        # Check for multiple Args sections (warning)
        if docstring.count("Args:") > 1:
            warnings.warn("Multiple 'Args:' sections found in the docstring.")

        tool_info = Tool(
            name=func.__name__,
            detail=main_description,
            parameters=parameters,
        )
        return tool_info 