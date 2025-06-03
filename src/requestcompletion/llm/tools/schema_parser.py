"""
JSON schema parsing utilities.

This module contains functions for parsing JSON schemas into Parameter objects
and converting Parameter objects into Pydantic models.
"""

from typing import Dict, Set, Type, List

from pydantic import BaseModel, Field, create_model, ConfigDict

from .parameter import Parameter, PydanticParameter


def parse_json_schema_to_parameter(
    name: str, prop_schema: dict, required: bool
) -> Parameter:
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

    param_type = prop_schema.get("type", "object")

    # Handle special case for number type
    if "type" in prop_schema and prop_schema["type"] == "number":
        param_type = "float"

    description = prop_schema.get("description", "")

    # Handle references to other schemas
    if "$ref" in prop_schema:
        # This is a reference to another schema, likely a nested model
        return PydanticParameter(
            name=name,
            param_type="object",
            description=description,
            required=required,
            properties={},  # Empty properties for now, will be filled later
        )

    # Handle nested objects.
    if param_type == "object" and "properties" in prop_schema:
        inner_required = prop_schema.get("required", [])
        inner_props = {}
        for inner_name, inner_schema in prop_schema["properties"].items():
            inner_props[inner_name] = parse_json_schema_to_parameter(
                inner_name, inner_schema, inner_name in inner_required
            )
        return PydanticParameter(
            name=name,
            param_type="object",
            description=description,
            required=required,
            properties=inner_props,
        )

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
            return PydanticParameter(
                name=name,
                param_type="array",
                description=description,
                required=required,
                properties=inner_props,
            )
        else:
            return Parameter(
                name=name,
                param_type="array",
                description=description,
                required=required,
            )
    else:
        return Parameter(
            name=name, param_type=param_type, description=description, required=required
        )


def parse_model_properties(schema: dict) -> Dict[str, Parameter]:  # noqa: C901
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
            "required": nested_required,
        }

    # Process main properties
    for prop_name, prop_schema in schema.get("properties", {}).items():
        # Check if this property references a nested model
        if "$ref" in prop_schema:
            ref = prop_schema["$ref"]
            if ref.startswith("#/$defs/"):
                model_name = ref[len("#/$defs/") :]
                if model_name in nested_models:
                    # Create a PydanticParameter with the nested model's properties
                    result[prop_name] = PydanticParameter(
                        name=prop_name,
                        param_type="object",
                        description=prop_schema.get("description", ""),
                        required=prop_name in required_fields,
                        properties=nested_models[model_name]["properties"],
                    )
                    continue
        elif "allOf" in prop_schema:
            for item in prop_schema.get("allOf", []):
                if "$ref" in item:
                    # Extract the model name from the reference
                    ref = item["$ref"]
                    if ref.startswith("#/$defs/"):
                        model_name = ref[len("#/$defs/") :]
                        if model_name in nested_models:
                            # Create a PydanticParameter with the nested model's properties
                            result[prop_name] = PydanticParameter(
                                name=prop_name,
                                param_type="object",
                                description=prop_schema.get("description", ""),
                                required=prop_name in required_fields,
                                properties=nested_models[model_name]["properties"],
                            )
                            break

        # If not already processed as a reference
        if prop_name not in result:
            # Get the correct type from the schema
            param_type = prop_schema.get("type", "object")

            # Handle special case for number type
            if "type" in prop_schema and prop_schema["type"] == "number":
                param_type = "float"

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
                    properties=inner_props,
                )
            else:
                result[prop_name] = parse_json_schema_to_parameter(
                    prop_name, prop_schema, prop_name in required_fields
                )

    return result


def convert_params_to_model_recursive(  # noqa: C901
    model_name: str, parameters: Set[Parameter]
) -> Type[BaseModel]:
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
                nested_model = convert_params_to_model_recursive(
                    f"{model_name}_{param.name}", set(param.properties.values())
                )
                python_type = nested_model
            elif param.param_type.lower() == "array":
                nested_model = convert_params_to_model_recursive(
                    f"{model_name}_{param.name}", set(param.properties.values())
                )
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

        # Handle optional parameters
        if not param.required:
            from typing import Optional as OptionalType

            python_type = OptionalType[python_type]

        field_definitions[param.name] = (
            python_type,
            Field(
                description=param.description,
                default=None if not param.required else ...,
            ),
        )

    # Create a model with model_config that sets extra="forbid" to ensure additionalProperties=False in the schema
    # TODO: This is a requirement by OpenAI's API, need to keep an eye out for other LLMs that may not have this requirement
    config = ConfigDict(extra="forbid")

    model = create_model(model_name, __config__=config, **field_definitions)
    return model
