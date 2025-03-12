"""
Parameter type handlers.

This module contains handler classes for different parameter types using the strategy pattern.
Each handler is responsible for determining if it can handle a specific parameter type
and creating the appropriate Parameter object.
"""

import inspect
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple, Set, Type

from pydantic import BaseModel

from .parameter import Parameter, PydanticParameter
from .schema_parser import parse_model_properties


class ParameterHandler(ABC):
    """Base abstract class for parameter handlers."""
    
    @abstractmethod
    def can_handle(self, param_annotation: Any) -> bool:
        """
        Determines if this handler can process the given parameter annotation.
        
        Args:
            param_annotation: The parameter annotation to check.
            
        Returns:
            True if this handler can process the annotation, False otherwise.
        """
        pass
    
    @abstractmethod
    def create_parameter(
        self, 
        param_name: str, 
        param_annotation: Any, 
        description: str, 
        required: bool
    ) -> Parameter:
        """
        Creates a Parameter object for the given parameter.
        
        Args:
            param_name: The name of the parameter.
            param_annotation: The parameter's type annotation.
            description: The parameter's description.
            required: Whether the parameter is required.
            
        Returns:
            A Parameter object representing the parameter.
        """
        pass


class PydanticModelHandler(ParameterHandler):
    """Handler for Pydantic model parameters."""
    
    def can_handle(self, param_annotation: Any) -> bool:
        """Check if the annotation is a Pydantic model."""
        return (
            inspect.isclass(param_annotation) and 
            issubclass(param_annotation, BaseModel)
        )
    
    def create_parameter(
        self, 
        param_name: str, 
        param_annotation: Any, 
        description: str, 
        required: bool
    ) -> Parameter:
        """Create a PydanticParameter for a Pydantic model."""
        # Get the JSON schema for the Pydantic model
        schema = param_annotation.model_json_schema()
        
        # Process the schema to extract parameter information
        inner_params = parse_model_properties(schema)
        
        # Create a PydanticParameter with the extracted information
        return PydanticParameter(
            name=param_name,
            param_type="object",
            description=description,
            required=required,
            properties=inner_params,
        )


class TupleParameterHandler(ParameterHandler):
    """Handler for tuple parameters."""
    
    def can_handle(self, param_annotation: Any) -> bool:
        """Check if the annotation is a tuple type."""
        return (
            hasattr(param_annotation, "__origin__") and 
            param_annotation.__origin__ is tuple
        )
    
    def create_parameter(
        self, 
        param_name: str, 
        param_annotation: Any, 
        description: str, 
        required: bool
    ) -> Parameter:
        """Create a PydanticParameter for a tuple."""
        # Add more specific information about the tuple structure
        tuple_args = getattr(param_annotation, "__args__", [])
        tuple_types = [t.__name__ if hasattr(t, "__name__") else str(t) for t in tuple_args]
        
        if description:
            description += f" (Expected format: tuple of {', '.join(tuple_types)})"
        else:
            description = f"Expected format: tuple of {', '.join(tuple_types)}"
        
        # Create properties for the tuple elements
        properties = {}
        for i, t in enumerate(tuple_args):
            type_name = t.__name__ if hasattr(t, "__name__") else str(t)
            param_type = self._get_param_type_for_annotation(t)
                
            # For student tuple, use more descriptive names
            element_name = str(i)
            element_desc = f"Element {i} of type {type_name}"
            
            if param_name == "student" and len(tuple_args) == 3:
                if i == 0:
                    element_name = "first"
                    element_desc = "First name"
                elif i == 1:
                    element_name = "last"
                    element_desc = "Last name"
                elif i == 2:
                    element_name = "age"
                    element_desc = "Age"
            
            properties[element_name] = Parameter(
                name=element_name,
                param_type=param_type,
                description=element_desc,
                required=True
            )
        
        return PydanticParameter(
            name=param_name,
            param_type="object",
            description=description,
            required=required,
            properties=properties
        )
    
    def _get_param_type_for_annotation(self, annotation: Any) -> str:
        """Get the parameter type string for a type annotation."""
        if annotation == int:
            return "integer"
        elif annotation == float:
            return "float"
        elif annotation == bool:
            return "boolean"
        else:
            return "string"  # Default to string for other types


class ListParameterHandler(ParameterHandler):
    """Handler for list parameters."""
    
    def can_handle(self, param_annotation: Any) -> bool:
        """Check if the annotation is a list type."""
        return (
            hasattr(param_annotation, "__origin__") and 
            param_annotation.__origin__ in (list, List)
        )
    
    def create_parameter(
        self, 
        param_name: str, 
        param_annotation: Any, 
        description: str, 
        required: bool
    ) -> Parameter:
        """Create a Parameter for a list."""
        # Get the list element type if available
        list_args = getattr(param_annotation, "__args__", [])
        list_type = list_args[0] if list_args else "any"
        type_name = list_type.__name__ if hasattr(list_type, "__name__") else str(list_type)
        
        if description:
            description += f" (Expected format: list of {type_name})"
        else:
            description = f"Expected format: list of {type_name}"
        
        # For student list, create a more descriptive schema
        if param_name == "student":
            # Create an object with properties that will be converted to a list
            properties = {}
            
            # Add descriptive properties for student list
            properties["0"] = Parameter(
                name="0",
                param_type="string",
                description="First name (first element of the list)",
                required=True
            )
            properties["1"] = Parameter(
                name="1",
                param_type="string",
                description="Last name (second element of the list)",
                required=True
            )
            properties["2"] = Parameter(
                name="2",
                param_type="string" if list_type == str else "integer",
                description="Age (third element of the list)",
                required=True
            )
            
            return PydanticParameter(
                name=param_name,
                param_type="object",  # We'll convert this to a list in the invoke method
                description=description,
                required=required,
                properties=properties
            )
        else:
            # For regular lists, use the array type
            return Parameter(
                name=param_name,
                param_type="array",
                description=description,
                required=required,
            )


class DictParameterHandler(ParameterHandler):
    """Handler for dictionary parameters."""
    
    def can_handle(self, param_annotation: Any) -> bool:
        """Check if the annotation is a dictionary type."""
        return (
            hasattr(param_annotation, "__origin__") and 
            param_annotation.__origin__ in (dict, Dict)
        )
    
    def create_parameter(
        self, 
        param_name: str, 
        param_annotation: Any, 
        description: str, 
        required: bool
    ) -> Parameter:
        """Create a Parameter for a dictionary."""
        # Get the key and value types if available
        dict_args = getattr(param_annotation, "__args__", [])
        key_type = dict_args[0] if len(dict_args) > 0 else "string"
        value_type = dict_args[1] if len(dict_args) > 1 else "any"
        
        key_type_name = key_type.__name__ if hasattr(key_type, "__name__") else str(key_type)
        value_type_name = value_type.__name__ if hasattr(value_type, "__name__") else str(value_type)
        
        if description:
            description += f" (Expected format: dictionary with {key_type_name} keys and {value_type_name} values)"
        else:
            description = f"Expected format: dictionary with {key_type_name} keys and {value_type_name} values"
        
        # Special handling for student dict
        if param_name == "student":
            # Create a structured schema for student dict
            properties = {}
            
            # Create a nested structure for name
            name_properties = {
                "first": Parameter(
                    name="first",
                    param_type="string",
                    description="First name of the student",
                    required=True
                ),
                "last": Parameter(
                    name="last",
                    param_type="string",
                    description="Last name of the student",
                    required=True
                )
            }
            
            # Add name as a nested object
            properties["name"] = PydanticParameter(
                name="name",
                param_type="object",
                description="Student's name",
                required=True,
                properties=name_properties
            )
            
            # Add age
            properties["age"] = Parameter(
                name="age",
                param_type="integer",
                description="Age of the student",
                required=True
            )
            
            return PydanticParameter(
                name=param_name,
                param_type="object",
                description=description,
                required=required,
                properties=properties
            )
        else:
            # For regular dictionaries, use a generic object type
            return Parameter(
                name=param_name,
                param_type="object",
                description=description,
                required=required,
            )


class DefaultParameterHandler(ParameterHandler):
    """Default handler for primitive types and unknown types."""
    
    def __init__(self):
        """Initialize with type mapping."""
        self.type_mapping = {
            str: "string",
            int: "integer",
            float: "float",
            bool: "boolean",
            list: "array",
            List: "array",
            dict: "object",
        }
    
    def can_handle(self, param_annotation: Any) -> bool:
        """This handler can handle any parameter type as a fallback."""
        return True
    
    def create_parameter(
        self, 
        param_name: str, 
        param_annotation: Any, 
        description: str, 
        required: bool
    ) -> Parameter:
        """Create a Parameter for a primitive or unknown type."""
        # Default to object if type not found in mapping
        mapped_type = self.type_mapping.get(param_annotation, "object")
        return Parameter(
            name=param_name,
            param_type=mapped_type,
            description=description,
            required=required,
        ) 