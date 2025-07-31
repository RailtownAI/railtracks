"""
JSON output_schema parsing utilities.

This module contains functions for parsing JSON schemas into Parameter objects
and converting Parameter objects into Pydantic models.
"""

from typing import Dict

from .parameter import ArrayParameter, Parameter, PydanticParameter


def _extract_param_type(prop_schema: dict) -> str | list:
    """Extract parameter type from JSON output_schema, handling various formats."""
    param_type = prop_schema.get("type", None)
    if param_type is None:
        # If no type, try to infer from other keys
        if "properties" in prop_schema:
            param_type = "object"
        elif "items" in prop_schema:
            param_type = "array"
        else:
            param_type = "object"  # fallback

    # Handle type as list (union)
    if isinstance(param_type, list):
        # Convert to python types, e.g. ["string", "null"]
        param_type = [t if t != "null" else "none" for t in param_type]

    return param_type


def _extract_basic_properties(prop_schema: dict) -> tuple:
    """Extract basic properties from JSON output_schema."""
    description = prop_schema.get("description", "")
    enum = prop_schema.get("enum")
    default = prop_schema.get("default")
    additional_properties = prop_schema.get("additionalProperties", False)
    return description, enum, default, additional_properties


def _handle_ref_schema(
    name: str, prop_schema: dict, required: bool, description: str
) -> "PydanticParameter":
    """Handle $ref schemas."""
    return PydanticParameter(
        name=name,
        required=required,
        param_type="object",
        description=description,
        ref_path=prop_schema["$ref"],
    )


def _handle_all_of_schema(
    name: str,
    prop_schema: dict,
    required: bool,
    description: str,
    additional_properties: bool,
) -> tuple[PydanticParameter | None, str | list]:
    """Handle allOf schemas. Returns (parameter, updated_param_type)."""
    param_type = None
    # Only handle simple case: allOf with $ref or type
    for item in prop_schema["allOf"]:
        if "$ref" in item:
            # Reference to another output_schema
            return (
                PydanticParameter(
                    name=name,
                    param_type="object",
                    description=description,
                    required=required,
                    properties={},
                    additional_properties=additional_properties,
                ),
                None,
            )
        elif "type" in item:
            # Merge type info
            param_type = item["type"]
    return None, param_type


def _handle_any_of_schema(
    name: str,
    prop_schema: dict,
    required: bool,
    description: str,
    enum,
    default,
    additional_properties: bool,
) -> "Parameter":
    """Handle anyOf schemas (union types)."""
    types_list = []
    inner_props = set()
    for item in prop_schema["anyOf"]:
        t = item.get("type", "string")
        types_list.append(t if t != "null" else "none")
        if t == "object":
            inner_required = item.get("required", [])
            for inner_name, inner_schema in item["properties"].items():
                inner_props.add(
                    parse_json_schema_to_parameter(
                        inner_name, inner_schema, inner_name in inner_required
                    )
                )
    param_type = types_list
    if inner_props:
        return PydanticParameter(
            name=name,
            param_type=param_type,
            description=description,
            required=required,
            additional_properties=additional_properties,
            properties=inner_props,
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


def _handle_object_schema(
    name: str,
    prop_schema: dict,
    required: bool,
    description: str,
    additional_properties: bool,
) -> "PydanticParameter":
    """Handle object schemas with properties."""
    inner_required = prop_schema.get("required", [])
    inner_props = set()
    for inner_name, inner_schema in prop_schema["properties"].items():
        inner_props.add(
            parse_json_schema_to_parameter(
                inner_name, inner_schema, inner_name in inner_required
            )
        )
    return PydanticParameter(
        name=name,
        param_type="object",
        description=description,
        required=required,
        properties=inner_props,
        additional_properties=additional_properties,
    )


def _handle_array_schema(
    name: str,
    prop_schema: dict,
    required: bool,
    description: str,
    enum,
    default,
    additional_properties: bool,
) -> "Parameter":
    """Handle array schemas."""
    items_schema = prop_schema["items"]
    max_items = prop_schema.get("maxItems")
    if items_schema.get("type") == "object" and "properties" in items_schema:
        inner_required = items_schema.get("required", [])

        inner_props = set()
        for inner_name, inner_schema in items_schema["properties"].items():
            inner_props.add(
                parse_json_schema_to_parameter(
                    inner_name, inner_schema, inner_name in inner_required
                )
            )
        return ArrayParameter(
            name=name,
            param_type="object",  # so that the subprops can be parsed
            description=description,
            max_items=max_items,
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


def parse_json_schema_to_parameter(
    name: str, prop_schema: dict, required: bool
) -> "Parameter":
    """
    Given a JSON-output_schema for a property, returns a Parameter or PydanticParameter.
    If prop_schema defines nested properties, this is done recursively.

    Args:
        name: The name of the parameter.
        prop_schema: The JSON output_schema definition for the property.
        required: Whether the parameter is required.

    Returns:
        A Parameter or PydanticParameter object representing the output_schema.
    """
    param_type = _extract_param_type(prop_schema)
    description, enum, default, additional_properties = _extract_basic_properties(
        prop_schema
    )

    if isinstance(additional_properties, dict):
        prop_schema.update(additional_properties)

    # Handle references to other schemas, you just need $ref path and description
    if "$ref" in prop_schema:
        return _handle_ref_schema(name, prop_schema, required, description)

    # Handle allOf (merge schemas)
    if "allOf" in prop_schema:
        result, updated_param_type = _handle_all_of_schema(
            name, prop_schema, required, description, additional_properties
        )
        if result is not None:
            return result
        if updated_param_type is not None:
            param_type = updated_param_type

    # Handle anyOf (union types)
    if "anyOf" in prop_schema:
        return _handle_any_of_schema(
            name,
            prop_schema,
            required,
            description,
            enum,
            default,
            additional_properties,
        )

    # Handle nested objects
    if "object" in param_type and "properties" in prop_schema:
        return _handle_object_schema(
            name, prop_schema, required, description, additional_properties
        )

    # Handle arrays, potentially with nested objects
    elif param_type == "array" and "items" in prop_schema:
        return _handle_array_schema(
            name,
            prop_schema,
            required,
            description,
            enum,
            default,
            additional_properties,
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
    Given a JSON output_schema (usually from BaseModel.model_json_schema()),
    returns a dictionary mapping property names to Parameter objects.

    Args:
        schema: The JSON output_schema to parse.

    Returns:
        A dictionary mapping property names to Parameter objects.
    """
    result = set()
    required_fields = schema.get("required", [])

    # First, process any $defs (nested model definitions)
    defs = schema.get("$defs", {})
    nested_models = {}

    for def_name, def_schema in defs.items():
        # Parse each nested model definition
        nested_props = set()
        nested_required = def_schema.get("required", [])

        for prop_name, prop_schema in def_schema.get("properties", {}).items():
            nested_props.add(
                parse_json_schema_to_parameter(
                    prop_name, prop_schema, prop_name in nested_required
                )
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
                    result.add(
                        PydanticParameter(
                            name=prop_name,
                            param_type="object",
                            description=prop_schema.get("description", ""),
                            required=prop_name in required_fields,
                            properties=nested_models[model_name]["properties"],
                        )
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
                            result.add(
                                PydanticParameter(
                                    name=prop_name,
                                    param_type="object",
                                    description=prop_schema.get("description", ""),
                                    required=prop_name in required_fields,
                                    properties=nested_models[model_name]["properties"],
                                )
                            )
                            break

        # If not already processed as a reference
        if prop_name not in [p.name for p in result]:
            # Get the correct type from the output_schema
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
                result.add(
                    PydanticParameter(
                        name=prop_name,
                        param_type=param_type,
                        description=prop_schema.get("description", ""),
                        required=prop_name in required_fields,
                        properties=inner_props,
                    )
                )
            else:
                result.add(
                    parse_json_schema_to_parameter(
                        prop_name, prop_schema, prop_name in required_fields
                    )
                )

    return result
