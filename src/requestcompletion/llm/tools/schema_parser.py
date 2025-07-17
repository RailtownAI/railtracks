"""
JSON schema parsing utilities.

This module contains functions for parsing JSON schemas into Parameter objects
and converting Parameter objects into Pydantic models.
"""

from typing import Dict

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

    # Handle type as list (union/optional)
    param_type = prop_schema.get("type", None)
    if param_type is None:
        # If no type, try to infer from other keys
        if "properties" in prop_schema:
            param_type = "object"
        elif "items" in prop_schema:
            param_type = "array"
        else:
            param_type = "string"  # fallback

    # Handle special case for number type
    if param_type == "number":
        param_type = "float"

    # Handle type as list (union)
    if isinstance(param_type, list):
        # Convert to python types, e.g. ["string", "null"]
        param_type = [t if t != "null" else "none" for t in param_type]

    description = prop_schema.get("description", "")
    enum = prop_schema.get("enum")
    default = prop_schema.get("default")
    additional_properties = prop_schema.get("additionalProperties", False)

    # Handle references to other schemas
    if "$ref" in prop_schema:
        return PydanticParameter(
            name=name,
            param_type="object",
            description=description,
            required=required,
            properties={},
            additional_properties=additional_properties,
        )

    # Handle allOf (merge schemas)
    if "allOf" in prop_schema:
        # Only handle simple case: allOf with $ref or type
        for item in prop_schema["allOf"]:
            if "$ref" in item:
                # Reference to another schema
                return PydanticParameter(
                    name=name,
                    param_type="object",
                    description=description,
                    required=required,
                    properties={},
                    additional_properties=additional_properties,
                )
            elif "type" in item:
                # Merge type info
                param_type = item["type"]

    # Handle anyOf (union types)
    if "anyOf" in prop_schema:
        # Only handle simple case: anyOf with types
        types_list = []
        for item in prop_schema["anyOf"]:
            t = item.get("type")
            if t:
                types_list.append(t if t != "null" else "none")
        if types_list:
            param_type = types_list

    # Handle nested objects
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
            additional_properties=additional_properties,
        )

    # Handle arrays, potentially with nested objects
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
                additional_properties=additional_properties,
            )
        else:
            return Parameter(
                name=name,
                param_type="array",
                description=description,
                required=required,
                enum=enum,
                default=default,
                additional_properties=additional_properties,
            )
    else:
        return Parameter(
            name=name,
            param_type=param_type,
            description=description,
            required=required,
            enum=enum,
            default=default,
            additional_properties=additional_properties,
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
