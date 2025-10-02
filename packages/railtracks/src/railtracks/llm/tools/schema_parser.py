from typing import Set

from .docstring_parser import param_from_python_type
from .parameters import (
    ArrayParameter,
    ObjectParameter,
    Parameter,
    RefParameter,
    UnionParameter,
)


def _extract_param_type(prop_schema: dict) -> str | list:
    param_type = prop_schema.get("type", None)

    if param_type is None:
        if "properties" in prop_schema:
            param_type = "object"
        elif "items" in prop_schema:
            param_type = "array"
        else:
            param_type = "object"

    if isinstance(param_type, list):
        # Convert "null" to "none" to match Parameter typing convention
        param_type = [t if t != "null" else "none" for t in param_type]

    return param_type


def _extract_basic_properties(prop_schema: dict):
    description = prop_schema.get("description", "")
    enum = prop_schema.get("enum", None)
    # Detect presence of "default" key alongside its value, including explicit null
    default_present = "default" in prop_schema
    default = prop_schema.get("default", None)
    additional_properties = prop_schema.get("additionalProperties", False)
    return description, enum, default, additional_properties, default_present


def _handle_ref_schema(
    name: str, prop_schema: dict, required: bool, description: str
) -> RefParameter:
    return RefParameter(
        name=name,
        description=description,
        required=required,
        ref_path=prop_schema["$ref"],
    )


def _handle_all_of_schema(
    name: str,
    prop_schema: dict,
    required: bool,
    description: str,
    additional_properties: bool,
) -> tuple[Parameter | None, str | list | None]:
    param_type = None
    for item in prop_schema["allOf"]:
        if "$ref" in item:
            return (
                ObjectParameter(
                    name=name,
                    description=description,
                    required=required,
                    properties=[],
                    additional_properties=additional_properties,
                ),
                None,
            )
        elif "type" in item:
            param_type = item["type"]
    return None, param_type


def _handle_any_of_schema(
    name: str,
    prop_schema: dict,
    required: bool,
    description: str,
    default=None,
    default_present: bool = False,
) -> Parameter:
    options = []
    for idx, option_schema in enumerate(prop_schema.get("anyOf", [])):
        # Generate a unique, descriptive name for this option
        option_name = f"{name}_option_{idx}"
        option_param = parse_json_schema_to_parameter(
            option_name, option_schema, required=True
        )
        options.append(option_param)

    # Defensive: avoid nested UnionParameter in options; flatten if found
    flattened_options = []
    for opt in options:
        if isinstance(opt, UnionParameter):
            flattened_options.extend(opt.options)
        else:
            flattened_options.append(opt)

    # If only one option, do not wrap in UnionParameter unnecessarily
    if len(flattened_options) == 1:
        return flattened_options[0]

    return UnionParameter(
        name=name,
        options=flattened_options,
        description=description,
        required=required,
        default=default,
        default_present=default_present,
    )


def _handle_object_schema(
    name: str,
    prop_schema: dict,
    required: bool,
    description: str,
    additional_properties: bool = False,
    default=None,
) -> Parameter:
    inner_required = prop_schema.get("required", [])
    inner_props = [
        parse_json_schema_to_parameter(
            inner_name, inner_schema, inner_name in inner_required
        )
        for inner_name, inner_schema in prop_schema.get("properties", {}).items()
    ]

    return ObjectParameter(
        name=name,
        description=description or prop_schema.get("description"),
        required=required,
        properties=inner_props,
        additional_properties=prop_schema.get(
            "additionalProperties", additional_properties
        ),
        default=default or prop_schema.get("default"),
    )


def _handle_array_schema(
    name: str,
    prop_schema: dict,
    required: bool,
    description: str,
    default,
    additional_properties: bool,
) -> Parameter:
    items_schema = prop_schema["items"]
    max_items = prop_schema.get("maxItems")

    if items_schema.get("type") == "object" and "properties" in items_schema:
        inner_required = items_schema.get("required", [])
        # Use ObjectParameter instead of PydanticParameter here
        item_param = ObjectParameter(
            name=f"{name}_item",
            description=items_schema.get("description", ""),
            required=True,
            properties=[
                parse_json_schema_to_parameter(
                    inner_name, inner_schema, inner_name in inner_required
                )
                for inner_name, inner_schema in items_schema["properties"].items()
            ],
            additional_properties=items_schema.get("additionalProperties", False),
        )
        return ArrayParameter(
            name=name,
            description=description,
            required=required,
            max_items=max_items,
            items=item_param,
            additional_properties=additional_properties,
            default=default,
        )
    else:
        # Handle primitive items as before
        item_type = items_schema.get("type", "string")
        item_param = Parameter(
            name=f"{name}_item",
            param_type=item_type,
            description=items_schema.get("description", ""),
            required=True,
            enum=items_schema.get("enum"),
            default=items_schema.get("default"),
        )
        return ArrayParameter(
            name=name,
            description=description,
            required=required,
            max_items=max_items,
            items=item_param,
            additional_properties=additional_properties,
            default=default,
        )


def parse_json_schema_to_parameter(
    name: str, prop_schema: dict, required: bool
) -> Parameter:
    """
    Parse a JSON schema property dict into a Parameter subclass instance properly.
    """
    param_type = _extract_param_type(prop_schema)
    description, enum, default, additional_properties, default_present = (
        _extract_basic_properties(prop_schema)
    )

    # Patch additionalProperties dict into schema if needed (you can adjust based on your needs)
    if isinstance(additional_properties, dict):
        prop_schema.update(additional_properties)
        additional_properties = True

    if "$ref" in prop_schema:
        return _handle_ref_schema(name, prop_schema, required, description)

    if "allOf" in prop_schema:
        result, updated_param_type = _handle_all_of_schema(
            name, prop_schema, required, description, additional_properties
        )
        if result is not None:
            return result
        if updated_param_type is not None:
            param_type = updated_param_type

    if "anyOf" in prop_schema:
        return _handle_any_of_schema(
            name,
            prop_schema,
            required,
            description,
            default,
            default_present,
        )

    if (
        param_type == "object"
        or (isinstance(param_type, list) and "object" in param_type)
    ) and "properties" in prop_schema:
        return _handle_object_schema(
            name, prop_schema, required, description, additional_properties
        )

    elif param_type == "array" and "items" in prop_schema:
        return _handle_array_schema(
            name,
            prop_schema,
            required,
            description,
            default,
            additional_properties,
        )

    else:
        # For simple types, use Parameter
        if isinstance(param_type, list):
            # If type is a list, create UnionParameter (e.g. ["string","none"])
            options = [param_from_python_type(t) for t in param_type]
            return UnionParameter(
                name=name,
                options=options,
                description=description,
                required=required,
                default=default,
                enum=enum,
                default_present=default_present,
            )
        else:
            return Parameter(
                name=name,
                param_type=param_type,
                description=description,
                required=required,
                enum=enum,
                default=default,
                default_present=default_present,
            )


def parse_model_properties(schema: dict) -> list[Parameter]:
    """
    Given a JSON schema (usually from BaseModel.model_json_schema()),
    returns a set of Parameter objects representing the top-level properties.
    """
    required_fields = schema.get("required", [])
    nested_models = _parse_model_defs(schema.get("$defs", {}))
    return _parse_main_properties(
        schema.get("properties", {}), required_fields, nested_models
    )


# --- Helper functions for parse_model_properties ---
def _parse_model_defs(defs: dict) -> dict:
    nested_models = {}
    for def_name, def_schema in defs.items():
        nested_required = def_schema.get("required", [])
        nested_props: Set[Parameter] = set()
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
    return nested_models


def _handle_ref_property(prop_name, prop_schema, required_fields, nested_models):
    ref = prop_schema["$ref"]
    if ref.startswith("#/$defs/"):
        model_name = ref[len("#/$defs/") :]
        if model_name in nested_models:
            return ObjectParameter(
                name=prop_name,
                description=prop_schema.get("description", ""),
                required=prop_name in required_fields,
                properties=nested_models[model_name]["properties"],
                additional_properties=False,
            )
    return None


def _handle_allof_property(prop_name, prop_schema, required_fields, nested_models):
    for item in prop_schema.get("allOf", []):
        if "$ref" in item:
            ref = item["$ref"]
            if ref.startswith("#/$defs/"):
                model_name = ref[len("#/$defs/") :]
                if model_name in nested_models:
                    return ObjectParameter(
                        name=prop_name,
                        description=prop_schema.get("description", ""),
                        required=prop_name in required_fields,
                        properties=nested_models[model_name]["properties"],
                        additional_properties=False,
                    )
    return None


def _handle_object_property(prop_name, prop_schema, required_fields):
    inner_required = prop_schema.get("required", [])
    inner_props = [
        parse_json_schema_to_parameter(
            inner_name, inner_schema, inner_name in inner_required
        )
        for inner_name, inner_schema in prop_schema["properties"].items()
    ]
    return ObjectParameter(
        name=prop_name,
        description=prop_schema.get("description", ""),
        required=prop_name in required_fields,
        properties=inner_props,
        additional_properties=prop_schema.get("additionalProperties", False),
    )


def _parse_main_properties(
    properties: dict, required_fields: list, nested_models: dict
) -> list[Parameter]:
    result = []
    for prop_name, prop_schema in properties.items():
        # Handle references to nested models in $defs
        if "$ref" in prop_schema:
            ref_obj = _handle_ref_property(
                prop_name, prop_schema, required_fields, nested_models
            )
            if ref_obj is not None:
                result.append(ref_obj)
                continue

        # Handle allOf references to nested models
        if "allOf" in prop_schema:
            allof_obj = _handle_allof_property(
                prop_name, prop_schema, required_fields, nested_models
            )
            if allof_obj is not None:
                result.append(allof_obj)
                continue

        # If not processed by ref/allOf above:
        param_type = prop_schema.get("type", "object")
        if param_type == "number":
            param_type = "float"

        # If object with properties, parse as ObjectParameter
        if param_type == "object" and "properties" in prop_schema:
            result.append(
                _handle_object_property(prop_name, prop_schema, required_fields)
            )
        else:
            # Fallback to parsing as a simple parameter
            result.append(
                parse_json_schema_to_parameter(
                    prop_name, prop_schema, prop_name in required_fields
                )
            )
    return result
