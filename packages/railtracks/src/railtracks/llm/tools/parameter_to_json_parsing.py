from typing import Any, Dict
from . import ArrayParameter, Parameter, PydanticParameter
from ...exceptions.errors import NodeInvocationError

# ================ START Parameter to JSON Schema parsing ===============
def _create_base_prop_dict(p: "Parameter") -> Dict[str, Any]:
    """Create base property dictionary with type and description."""
    prop_dict = {
        "type": p.param_type,
    }

    if p.description:
        prop_dict["description"] = p.description

    return prop_dict


def _handle_array_type(prop_dict: Dict[str, Any], p: "Parameter") -> None:
    """Handle array type parameters."""
    element_type = (
        p.default or "string"
    )  # Default to 'string' if no element type is provided
    prop_dict["items"] = {"type": element_type}


def _handle_object_type(prop_dict: Dict[str, Any], p: "Parameter") -> None:
    """Handle object type parameters."""
    if (
        isinstance(p, PydanticParameter) and p.ref_path
    ):  # special case for $ref: we only need description and $ref
        prop_dict["$ref"] = p.ref_path
        prop_dict.pop("type")
    else:
        prop_dict["additionalProperties"] = p.additional_properties
        inner_props = getattr(
            p, "properties", set()
        )  # incase props are not present in the schema
        prop_dict["properties"] = _handle_set_of_parameters(inner_props, True)
        sub_required_params = [p.name for p in inner_props if p.required]
        if sub_required_params:
            prop_dict["required"] = sub_required_params


def _handle_union_type(prop_dict: Dict[str, Any], p: "Parameter") -> None:
    """Handle union/list type parameters."""
    any_of_list = []
    for t in p.param_type:
        t = (
            "null" if t == "none" else t
        )  # none can only be found as a type for union/optional and we will convert it to null
        type_item = {"type": t}
        if t == "object":  # override type_item if object
            inner_props = getattr(
                p, "properties", set()
            )  # incase props are not present in the schema
            type_item["properties"] = _handle_set_of_parameters(inner_props, True)
            type_item["description"] = p.description
            type_item["additionalProperties"] = p.additional_properties
        any_of_list.append(type_item)
    prop_dict["anyOf"] = any_of_list
    prop_dict.pop("type")


def _handle_array_parameter(
    p: "ArrayParameter", prop_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """Handle ArrayParameter instances with special array wrapping."""
    items_schema = {"type": "array"}
    if p.description:
        items_schema["description"] = p.description
        prop_dict.pop("description")
    items_schema["items"] = prop_dict
    if p.max_items:
        items_schema["maxItems"] = p.max_items
    return items_schema


def _set_parameter_defaults(prop_dict: Dict[str, Any], p: "Parameter") -> None:
    """Set default values and enum for parameters."""
    if (
        p.default is not None
    ):  # default can be 0 or False, if default value is supposed to be None, the param will be treated as optional
        prop_dict["default"] = p.default
    elif (
        isinstance(p.param_type, list) and "none" in p.param_type
    ):  # if param_type is list and none is in it, the param is optional and default is None
        prop_dict["default"] = None

    if p.enum:
        prop_dict["enum"] = p.enum


def _process_single_parameter(p: "Parameter") -> tuple[str, Dict[str, Any], bool]:
    """Process a single parameter and return (name, prop_dict, is_required)."""
    prop_dict = _create_base_prop_dict(p)

    # Handle different parameter types
    if p.param_type == "array":
        _handle_array_type(prop_dict, p)

    if p.param_type == "object":
        _handle_object_type(prop_dict, p)

    if isinstance(p.param_type, list):
        _handle_union_type(prop_dict, p)

    # Handle ArrayParameter wrapper
    if isinstance(p, ArrayParameter):
        prop_dict = _handle_array_parameter(p, prop_dict)

    # Set defaults and enum
    _set_parameter_defaults(prop_dict, p)

    return p.name, prop_dict, p.required


def _build_final_schema(
    props: Dict[str, Any], required: list[str], sub_property: bool
) -> Dict[str, Any]:
    """Build the final output_schema dictionary."""
    if sub_property:
        return props
    else:
        model_schema: Dict[str, Any] = {
            "type": "object",
            "properties": props,
        }
        if required:
            model_schema["required"] = required
        return model_schema


def _handle_set_of_parameters(
    parameters: List[Parameter | PydanticParameter | ArrayParameter],
    sub_property: bool = False,
) -> Dict[str, Any]:
    """Handle the case where parameters are a set of Parameter instances."""
    props: Dict[str, Any] = {}
    required: list[str] = []

    for p in parameters:
        name, prop_dict, is_required = _process_single_parameter(p)
        props[name] = prop_dict

        if is_required:
            required.append(name)

    return _build_final_schema(props, required, sub_property)


# ================================= END Parameter to JSON Schema parsing ===================================


def _parameters_to_json_schema(
    parameters: list[Parameter] | set[Parameter] | None,
) -> Dict[str, Any]:
    """
    Turn a set of Parameter instances
    into a JSON Schema dict accepted by litellm.completion.
    """
    if parameters is None:
        return {}
    elif isinstance(parameters, list) and all(
        isinstance(x, Parameter) for x in parameters
    ):
        return _handle_set_of_parameters(parameters)
    elif isinstance(parameters, set) and all(
        isinstance(x, Parameter) for x in parameters
    ):
        return _handle_set_of_parameters(list(parameters))

    raise NodeInvocationError(
        message=f"Unable to parse Tool.parameters. It was {parameters}",
        fatal=True,
        notes=[
            "Tool.parameters must be a set of Parameter objects",
        ],
    )