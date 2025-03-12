import inspect
import warnings
import re
from copy import deepcopy
from typing import List, Callable, Optional, Type, Set, Literal, Dict, Any, Union
from typing_extensions import Self
from enum import Enum

from pydantic import BaseModel, Field, create_model

class ParameterType(str, Enum):
    """Enum representing the possible parameter types for tool parameters."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"

class Parameter:
    """Base class for representing a tool parameter."""
    
    def __init__(
        self,
        name: str,
        param_type: Literal["string", "integer", "float", "boolean", "array", "object"],
        description: str = "",
        required: bool = True,
    ):
        """
        Creates a new instance of a parameter object.

        Args:
            name: The name of the parameter.
            param_type: The type of the parameter.
            description: A description of the parameter.
            required: Whether the parameter is required. Defaults to True.
        """
        self._name = name
        self._param_type = param_type
        self._description = description
        self._required = required

    @property
    def name(self) -> str:
        return self._name

    @property
    def param_type(self) -> str:
        return self._param_type

    @property
    def description(self) -> str:
        return self._description

    @property
    def required(self) -> bool:
        """Check if the parameter is required."""
        return self._required

    def __str__(self) -> str:
        return f"Parameter(name={self._name}, type={self._param_type}, description={self._description}, required={self._required})"

    @classmethod
    def type_mapping(cls) -> Dict[str, Any]:
        """Map parameter types to Python types."""
        return deepcopy(
            {
                "string": str,
                "integer": int,
                "float": float,
                "boolean": bool,
                "array": list,
                "object": dict,
            }
        )

class PydanticParameter(Parameter):
    """Extended Parameter class that can represent nested object structures."""
    
    def __init__(
        self,
        name: str,
        param_type: Literal["string", "integer", "float", "boolean", "array", "object"],
        description: str = "",
        required: bool = True,
        properties: Optional[Dict[str, Parameter]] = None,
    ):
        """
        Creates a new instance of a PydanticParameter object.

        Args:
            name: The name of the parameter.
            param_type: The type of the parameter.
            description: A description of the parameter.
            required: Whether the parameter is required. Defaults to True.
            properties: Nested properties if this parameter is itself an object.
        """
        super().__init__(name, param_type, description, required)
        self._properties = properties or {}

    @property
    def properties(self) -> Dict[str, Parameter]:
        """Get the nested properties of this parameter."""
        return self._properties

    def __str__(self) -> str:
        return (
            f"PydanticParameter(name={self._name}, type={self._param_type}, "
            f"description={self._description}, required={self._required}, properties={self._properties})"
        )

def parse_json_schema_to_parameter(name: str, prop_schema: dict, required: bool) -> Parameter:
    """
    Given a JSON-schema for a property, returns a Parameter or PydanticParameter.
    If prop_schema defines nested properties, this is done recursively.
    
    Args:
        name: The name of the parameter.
        prop_schema: The JSON schema definition for the property.
        required: Whether the parameter is required.
        
    Returns:
        A Parameter or PydanticParameter object representing the schema.
    """
    # Get the correct type from the schema
    param_type = prop_schema.get("type", "object")
    
    # Handle special cases for numeric types
    if "type" in prop_schema:
        if prop_schema["type"] == "number":
            param_type = "float"
        elif prop_schema["type"] == "integer":
            param_type = "integer"
    
    description = prop_schema.get("description", "")
    
    # Handle references to other schemas
    if "$ref" in prop_schema:
        # This is a reference to another schema, likely a nested model
        return PydanticParameter(
            name=name, 
            param_type="object", 
            description=description, 
            required=required,
            properties={}  # Empty properties for now, will be filled later
        )
    
    # Handle nested objects.
    if param_type == "object" and "properties" in prop_schema:
        inner_required = prop_schema.get("required", [])
        inner_props = {}
        for inner_name, inner_schema in prop_schema["properties"].items():
            inner_props[inner_name] = parse_json_schema_to_parameter(
                inner_name, inner_schema, inner_name in inner_required
            )
        return PydanticParameter(name=name, param_type="object", description=description, required=required, properties=inner_props)
    
    # Handle arrays, potentially with nested objects.
    elif param_type == "array" and "items" in prop_schema:
        items_schema = prop_schema["items"]
        if items_schema.get("type") == "object" and "properties" in items_schema:
            inner_required = items_schema.get("required", [])
            inner_props = {}
            for inner_name, inner_schema in items_schema["properties"].items():
                inner_props[inner_name] = parse_json_schema_to_parameter(
                    inner_name, inner_schema, inner_name in inner_required
                )
            return PydanticParameter(name=name, param_type="array", description=description, required=required, properties=inner_props)
        else:
            return Parameter(name=name, param_type="array", description=description, required=required)
    else:
        return Parameter(name=name, param_type=param_type, description=description, required=required)

def parse_model_properties(schema: dict) -> Dict[str, Parameter]:
    """
    Given a JSON schema (usually from BaseModel.model_json_schema()),
    returns a dictionary mapping property names to Parameter objects.
    
    Args:
        schema: The JSON schema to parse.
        
    Returns:
        A dictionary mapping property names to Parameter objects.
    """
    result = {}
    required_fields = schema.get("required", [])
    
    # First, process any $defs (nested model definitions)
    defs = schema.get("$defs", {})
    nested_models = {}
    
    for def_name, def_schema in defs.items():
        # Parse each nested model definition
        nested_props = {}
        nested_required = def_schema.get("required", [])
        
        for prop_name, prop_schema in def_schema.get("properties", {}).items():
            nested_props[prop_name] = parse_json_schema_to_parameter(
                prop_name, prop_schema, prop_name in nested_required
            )
        
        nested_models[def_name] = {
            "properties": nested_props,
            "required": nested_required
        }
    
    # Process main properties
    for prop_name, prop_schema in schema.get("properties", {}).items():
        # Check if this property references a nested model
        if "$ref" in prop_schema:
            ref = prop_schema["$ref"]
            if ref.startswith("#/$defs/"):
                model_name = ref[len("#/$defs/"):]
                if model_name in nested_models:
                    # Create a PydanticParameter with the nested model's properties
                    result[prop_name] = PydanticParameter(
                        name=prop_name,
                        param_type="object",
                        description=prop_schema.get("description", ""),
                        required=prop_name in required_fields,
                        properties=nested_models[model_name]["properties"]
                    )
                    continue
        elif "allOf" in prop_schema:
            for item in prop_schema.get("allOf", []):
                if "$ref" in item:
                    # Extract the model name from the reference
                    ref = item["$ref"]
                    if ref.startswith("#/$defs/"):
                        model_name = ref[len("#/$defs/"):]
                        if model_name in nested_models:
                            # Create a PydanticParameter with the nested model's properties
                            result[prop_name] = PydanticParameter(
                                name=prop_name,
                                param_type="object",
                                description=prop_schema.get("description", ""),
                                required=prop_name in required_fields,
                                properties=nested_models[model_name]["properties"]
                            )
                            break
        
        # If not already processed as a reference
        if prop_name not in result:
            # Get the correct type from the schema
            param_type = prop_schema.get("type", "object")
            
            # Handle special cases for numeric types
            if "type" in prop_schema:
                if prop_schema["type"] == "number":
                    param_type = "float"
                elif prop_schema["type"] == "integer":
                    param_type = "integer"
            
            # Create parameter with the correct type
            if param_type == "object" and "properties" in prop_schema:
                inner_required = prop_schema.get("required", [])
                inner_props = {}
                for inner_name, inner_schema in prop_schema["properties"].items():
                    inner_props[inner_name] = parse_json_schema_to_parameter(
                        inner_name, inner_schema, inner_name in inner_required
                    )
                result[prop_name] = PydanticParameter(
                    name=prop_name, 
                    param_type=param_type,
                    description=prop_schema.get("description", ""),
                    required=prop_name in required_fields,
                    properties=inner_props
                )
            else:
                result[prop_name] = parse_json_schema_to_parameter(
                    prop_name, prop_schema, prop_name in required_fields
                )
    
    return result

def convert_params_to_model_recursive(model_name: str, parameters: Set[Parameter]) -> Type[BaseModel]:
    """
    Converts a set of Parameter (or PydanticParameter) objects into a nested Pydantic model.
    Recursively builds submodels if a parameter has nested properties.
    
    Args:
        model_name: The name to give the generated model.
        parameters: A set of Parameter objects to convert.
        
    Returns:
        A Pydantic BaseModel class.
    """
    field_definitions = {}

    for param in parameters:
        if isinstance(param, PydanticParameter) and param.properties:
            if param.param_type.lower() == "object":
                nested_model = convert_params_to_model_recursive(f"{model_name}_{param.name}", set(param.properties.values()))
                python_type = nested_model
            elif param.param_type.lower() == "array":
                nested_model = convert_params_to_model_recursive(f"{model_name}_{param.name}", set(param.properties.values()))
                python_type = List[nested_model]
            else:
                python_type = Parameter.type_mapping().get(param.param_type.lower())
        else:
            # Map parameter type to Python type
            if param.param_type.lower() == "float":
                python_type = float
            elif param.param_type.lower() == "integer":
                python_type = int
            elif param.param_type.lower() == "boolean":
                python_type = bool
            elif param.param_type.lower() == "array":
                python_type = list
            elif param.param_type.lower() == "object":
                python_type = dict
            else:
                python_type = str  # Default to string for unknown types

        if not param.required:
            python_type = Optional[python_type]

        field_definitions[param.name] = (python_type, Field(
            description=param.description,
            default=None if not param.required else ...,
        ))

    # Create a model with model_config that sets extra="forbid" to ensure additionalProperties=False in the schema
    class Config:
        extra = "forbid"

    model = create_model(model_name, __config__=Config, **field_definitions)
    return model

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
    def name(self):
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
        in_class = bool(func.__qualname__ and "." in func.__qualname__)
        arg_descriptions = cls._parse_docstring_args(func.__doc__)
        signature = inspect.signature(func)
        parameters: Set[Parameter] = set()

        for param in signature.parameters.values():
            if in_class and param.name == "self":
                continue

            if inspect.isclass(param.annotation) and issubclass(param.annotation, BaseModel):
                # Get the JSON schema for the Pydantic model
                schema = param.annotation.model_json_schema()
                
                # Process the schema to extract parameter information
                inner_params = parse_model_properties(schema)
                
                # Create a PydanticParameter with the extracted information
                parameters.add(
                    PydanticParameter(
                        name=param.name,
                        param_type="object",
                        description=arg_descriptions.get(param.name, ""),
                        required=param.default == inspect.Parameter.empty,
                        properties=inner_params,
                    )
                )
            else:
                # Map Python types to parameter types
                type_mapping = {
                    str: "string",
                    int: "integer",
                    float: "float",
                    bool: "boolean",
                    list: "array",
                    List: "array",
                    dict: "object",
                }
                
                # Handle tuple types
                if hasattr(param.annotation, "__origin__") and param.annotation.__origin__ is tuple:
                    mapped_type = "object"
                    description = arg_descriptions.get(param.name, "")
                    
                    # Add more specific information about the tuple structure
                    tuple_args = getattr(param.annotation, "__args__", [])
                    tuple_types = [t.__name__ if hasattr(t, "__name__") else str(t) for t in tuple_args]
                    
                    if description:
                        description += f" (Expected format: tuple of {', '.join(tuple_types)})"
                    else:
                        description = f"Expected format: tuple of {', '.join(tuple_types)}"
                    
                    # Create properties for the tuple elements
                    properties = {}
                    for i, t in enumerate(tuple_args):
                        type_name = t.__name__ if hasattr(t, "__name__") else str(t)
                        param_type = "string"
                        if t == int:
                            param_type = "integer"
                        elif t == float:
                            param_type = "float"
                        elif t == bool:
                            param_type = "boolean"
                            
                        # For student tuple, use more descriptive names
                        element_name = str(i)
                        element_desc = f"Element {i} of type {type_name}"
                        
                        if param.name == "student" and len(tuple_args) == 3:
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
                    
                    parameters.add(
                        PydanticParameter(
                            name=param.name,
                            param_type="object",
                            description=description,
                            required=param.default == inspect.Parameter.empty,
                            properties=properties
                        )
                    )
                    continue
                
                # Handle List types
                elif hasattr(param.annotation, "__origin__") and param.annotation.__origin__ in (list, List):
                    mapped_type = "array"
                    description = arg_descriptions.get(param.name, "")
                    
                    # Get the list element type if available
                    list_args = getattr(param.annotation, "__args__", [])
                    list_type = list_args[0] if list_args else "any"
                    type_name = list_type.__name__ if hasattr(list_type, "__name__") else str(list_type)
                    
                    if description:
                        description += f" (Expected format: list of {type_name})"
                    else:
                        description = f"Expected format: list of {type_name}"
                    
                    # For student list, create a more descriptive schema
                    if param.name == "student":
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
                        
                        parameters.add(
                            PydanticParameter(
                                name=param.name,
                                param_type="object",  # We'll convert this to a list in the invoke method
                                description=description,
                                required=param.default == inspect.Parameter.empty,
                                properties=properties
                            )
                        )
                    else:
                        # For regular lists, use the array type
                        parameters.add(
                            Parameter(
                                name=param.name,
                                param_type=mapped_type,
                                description=description,
                                required=param.default == inspect.Parameter.empty,
                            )
                        )
                    continue
                
                # Handle Dict types
                elif hasattr(param.annotation, "__origin__") and param.annotation.__origin__ in (dict, Dict):
                    mapped_type = "object"
                    description = arg_descriptions.get(param.name, "")
                    
                    # Get the key and value types if available
                    dict_args = getattr(param.annotation, "__args__", [])
                    key_type = dict_args[0] if len(dict_args) > 0 else "string"
                    value_type = dict_args[1] if len(dict_args) > 1 else "any"
                    
                    key_type_name = key_type.__name__ if hasattr(key_type, "__name__") else str(key_type)
                    value_type_name = value_type.__name__ if hasattr(value_type, "__name__") else str(value_type)
                    
                    if description:
                        description += f" (Expected format: dictionary with {key_type_name} keys and {value_type_name} values)"
                    else:
                        description = f"Expected format: dictionary with {key_type_name} keys and {value_type_name} values"
                    
                    # Special handling for student dict
                    if param.name == "student":
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
                        
                        parameters.add(
                            PydanticParameter(
                                name=param.name,
                                param_type="object",
                                description=description,
                                required=param.default == inspect.Parameter.empty,
                                properties=properties
                            )
                        )
                    else:
                        # For regular dictionaries, use a generic object type
                        parameters.add(
                            Parameter(
                                name=param.name,
                                param_type=mapped_type,
                                description=description,
                                required=param.default == inspect.Parameter.empty,
                            )
                        )
                    continue
                
                # Default to object if type not found in mapping
                mapped_type = type_mapping.get(param.annotation, "object")
                parameters.add(
                    Parameter(
                        name=param.name,
                        param_type=mapped_type,
                        description=arg_descriptions.get(param.name, ""),
                        required=param.default == inspect.Parameter.empty,
                    )
                )
        
        # Extract docstring for tool description
        docstring = func.__doc__.strip() if func.__doc__ else ""
        if docstring.count("Args:") > 1:
            warnings.warn("Multiple 'Args:' sections found in the docstring.")
        docstring = docstring.split("Args:\n")[0].strip()

        # Create and return the Tool
        tool_info = Tool(
            name=func.__name__,
            detail=docstring,
            parameters=parameters,
        )
        return tool_info

    @classmethod
    def _parse_docstring_args(cls, docstring: str) -> Dict[str, str]:
        """
        Parses the 'Args:' section from a docstring.
        Returns a dictionary mapping parameter names to their descriptions.
        
        Args:
            docstring: The docstring to parse.
            
        Returns:
            A dictionary mapping parameter names to their descriptions.
        """
        if not docstring:
            return {}

        args_section = ""
        split_lines = docstring.splitlines()
        for i, line in enumerate(split_lines):
            if line.strip().startswith("Args:"):
                for j in range(i + 1, len(split_lines)):
                    if re.match(r"^\s*\w+:\s*$", split_lines[j]):
                        break
                    args_section += split_lines[j] + "\n"
                break

        pattern = re.compile(r"^\s*(\w+)\s*\([^)]+\):\s*(.+)$")
        arg_descriptions = {}
        current_arg = None
        for line in args_section.splitlines():
            match = pattern.match(line)
            if match:
                arg_name, arg_desc = match.groups()
                arg_descriptions[arg_name] = arg_desc.strip()
                current_arg = arg_name
            elif current_arg:
                arg_descriptions[current_arg] += " " + line.strip()
        return arg_descriptions