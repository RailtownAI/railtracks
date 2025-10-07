import inspect
from typing import Any, Callable, Dict, Iterable, get_origin

from pydantic import BaseModel
from railtracks.exceptions.errors import NodeCreationError
from railtracks.exceptions.messages.exception_messages import (
    ExceptionMessageKey,
    get_message,
    get_notes,
)
from railtracks.llm import Parameter, SystemMessage
from railtracks.llm.tools.parameters import ParameterType
from railtracks.utils.logging import get_rt_logger

# Global logger for validation
logger = get_rt_logger("Validation")


def validate_function(func: Callable) -> None:
    """
    Validate that the function is safe to use in a node.
    If there are any dict or Dict parameters, raise an error.
    Also checks recursively for any nested dictionary structures, including inside BaseModels.

    Args:
        func: The function to validate.

    Raises:
        NodeCreationError: If the function has dict or Dict parameters, even nested.
    """

    def check_for_nested_dict(annotation, param_name, path=""):
        origin = get_origin(annotation)
        # Direct dict or typing.Dict
        if annotation is dict or origin in (dict, Dict):
            notes = get_notes(ExceptionMessageKey.DICT_PARAMETER_NOT_ALLOWED_NOTES)
            notes[0] = notes[0].format(param_name=param_name, path=path)
            raise NodeCreationError(
                message=get_message(
                    ExceptionMessageKey.DICT_PARAMETER_NOT_ALLOWED_MSG
                ).format(param_name=param_name, path=path or param_name),
                notes=notes,
            )
        # If annotation is a subclass of BaseModel, check its fields recursively
        try:
            if isinstance(annotation, type) and issubclass(annotation, BaseModel):
                for field_name, field in annotation.__annotations__.items():
                    check_for_nested_dict(
                        field, param_name, f"{path or param_name}.{field_name}"
                    )
        except (
            AttributeError
        ):  # Only swallow attribute errors (e.g., __annotations__ missing)
            pass
        except Exception as e:  # if a nested error is caught, pass it along (includes passing up NodeCreationError)
            raise e

        args = getattr(annotation, "__args__", None)
        if args:
            for idx, arg in enumerate(args):
                nested_path = f"{path or param_name}[{idx}]"
                check_for_nested_dict(arg, param_name, nested_path)

    sig = inspect.signature(func)
    for param in sig.parameters.values():
        annotation = param.annotation
        check_for_nested_dict(annotation, param.name)


def check_classmethod(method: Any, method_name: str) -> None:
    """
    Ensure the given method is a classmethod.

    Args:
        method: The method to check.
        method_name: The name of the method (for error messages).

    Raises:
        NodeCreationError: If the method is not a classmethod.
    """
    if not isinstance(method, classmethod):
        raise NodeCreationError(
            message=get_message(ExceptionMessageKey.CLASSMETHOD_REQUIRED_MSG).format(
                method_name=method_name
            ),
            notes=[
                note.format(method_name=method_name)
                for note in get_notes(ExceptionMessageKey.CLASSMETHOD_REQUIRED_NOTES)
            ],
        )


def check_connected_nodes(node_set, node: type) -> None:
    """
    Validate that node_set is non-empty and contains only subclasses of Node or functions.

    Args:
        node_set: The set of nodes to check.
        node: The base Node class.

    Raises:
        NodeCreationError: If node_set is empty or contains invalid types.
    """
    if not node_set:
        raise NodeCreationError(
            message=get_message(ExceptionMessageKey.CONNECTED_NODES_EMPTY_MSG),
            notes=get_notes(ExceptionMessageKey.CONNECTED_NODES_EMPTY_NOTES),
        )
    elif not all((isinstance(x, type) and issubclass(x, node)) for x in node_set):
        raise NodeCreationError(
            message=get_message(ExceptionMessageKey.CONNECTED_NODES_TYPE_MSG),
            notes=get_notes(ExceptionMessageKey.CONNECTED_NODES_TYPE_NOTES),
        )


def check_schema(method: classmethod, cls: type) -> None:
    """
    Validate the output_schema returned by a classmethod.

    Args:
        method: The classmethod to call.
        cls: The class to pass to the method.

    Raises:
        NodeCreationError: If the output_schema is missing, invalid, or empty.
    """
    schema = method.__func__(cls)
    if not schema:
        raise NodeCreationError(
            message=get_message(ExceptionMessageKey.OUTPUT_MODEL_REQUIRED_MSG),
            notes=get_notes(ExceptionMessageKey.OUTPUT_MODEL_REQUIRED_NOTES),
        )
    elif not issubclass(schema, BaseModel):
        raise NodeCreationError(
            message=get_message(ExceptionMessageKey.OUTPUT_MODEL_TYPE_MSG).format(
                actual_type=type(schema)
            ),
            notes=get_notes(ExceptionMessageKey.OUTPUT_MODEL_TYPE_NOTES),
        )
    elif len(schema.model_fields) == 0:
        raise NodeCreationError(
            message=get_message(ExceptionMessageKey.OUTPUT_MODEL_EMPTY_MSG),
            notes=get_notes(ExceptionMessageKey.OUTPUT_MODEL_EMPTY_NOTES),
        )


# ========================= Common Validation accross easy_usage_wrappers ========================
def _check_duplicate_param_names(tool_params: Iterable[Any]) -> None:
    """
    Ensure all parameter names in tool_params are unique.

    Args:
        tool_params: Iterable of parameter objects with a 'name' attribute.

    Raises:
        NodeCreationError: If duplicate parameter names are found.
    """
    if tool_params:
        names = [x.name for x in tool_params]
        if len(names) != len(set(names)):
            raise NodeCreationError(
                message=get_message(ExceptionMessageKey.DUPLICATE_PARAMETER_NAMES_MSG),
                notes=get_notes(ExceptionMessageKey.DUPLICATE_PARAMETER_NAMES_NOTES),
            )


def _check_pretty_name(pretty_name: str | None, tool_details: Any) -> None:
    """
    Ensure a name is provided if tool_details exist.

    Args:
        pretty_name: The pretty name to check.
        tool_details: The tool details object.

    Raises:
        NodeCreationError: If name is missing when tool_details are present.
    """
    if pretty_name is None and tool_details:
        raise NodeCreationError(
            get_message(ExceptionMessageKey.MISSING_PRETTY_NAME_MSG)
        )


def _check_system_message(system_message: SystemMessage | None) -> None:
    """
    Validate that system_message is an instance of SystemMessageType if provided.
    Args:
        system_message: The system message to check.
        SystemMessageType: The expected type for system_message.
    Raises:
        NodeCreationError: If system_message is not of the correct type.
    """
    if system_message is not None and not isinstance(system_message, SystemMessage):
        raise NodeCreationError(
            get_message(ExceptionMessageKey.INVALID_SYSTEM_MESSAGE_MSG),
        )


def _check_tool_params_and_details(tool_params: Any, tool_details: Any) -> None:
    """
    Ensure tool_details are provided if tool_params exist.

    Args:
        tool_params: The tool parameters to check.
        tool_details: The tool details object.

    Raises:
        NodeCreationError: If tool_params exist but tool_details are missing.
    """
    if tool_params and not tool_details:
        raise NodeCreationError(
            get_message(ExceptionMessageKey.MISSING_TOOL_DETAILS_MSG),
            notes=get_notes(ExceptionMessageKey.MISSING_TOOL_DETAILS_NOTES),
        )


def _check_max_tool_calls(max_tool_calls: int | None) -> None:
    """
    Ensure max_tool_calls is a non-negative integer.
    Args:
        max_tool_calls: The maximum number of tool calls allowed.
    Raises:
        NodeCreationError: If max_tool_calls is negative.
    """
    if max_tool_calls is not None and max_tool_calls < 0:
        raise NodeCreationError(
            get_message(ExceptionMessageKey.MAX_TOOL_CALLS_NEGATIVE_MSG),
            notes=get_notes(ExceptionMessageKey.MAX_TOOL_CALLS_NEGATIVE_NOTES),
        )


def validate_tool_metadata(
    tool_params: Any,
    tool_details: Any,
    system_message: Any,
    pretty_name: str | None,
    max_tool_calls: int | None = None,
) -> None:
    """
    Run all tool metadata validation checks at once.

    Args:
        tool_params: The tool parameters to check.
        tool_details: The tool details object.
        system_message: The system message to check.
        pretty_name: The pretty name to check.
        max_tool_calls: The maximum number of tool calls allowed.

    Raises:
        NodeCreationError: If any validation fails.
    """
    _check_tool_params_and_details(tool_params, tool_details)
    _check_duplicate_param_names(tool_params or [])
    _check_system_message(system_message)
    _check_pretty_name(pretty_name, tool_details)
    _check_max_tool_calls(max_tool_calls)


# ================================================ END Common Validation accross easy_usage_wrappers ===========================================================


# ================================================================= START Tool init error ===========================================================
def validate_tool_params(parameters: Any, param_type) -> bool:
    if not (isinstance(parameters, (set, dict)) or parameters is None):
        raise NodeCreationError(
            message=get_message(ExceptionMessageKey.TOOL_PARAMETERS_TYPE_MSG),
            notes=get_notes(ExceptionMessageKey.TOOL_PARAMETERS_TYPE_NOTES),
        )

    if isinstance(parameters, dict) and len(parameters) > 0:
        try:
            assert "type" in parameters, (
                "A 'type' key must be provided in the JSON-output_schema."
            )
            assert parameters["type"] == "object", (
                "The outer-most 'type' must be 'object' in the JSON-output_schema."
            )
            assert "additionalProperties" in parameters, (
                "The 'additionalProperties' key must be present and set to False."
            )
            assert not parameters["additionalProperties"], (
                "The 'additionalProperties' must be set to False in the JSON-output_schema."
            )
            assert "properties" in parameters, (
                "A 'properties' key must be provided in the JSON-output_schema."
            )
        except AssertionError as e:
            raise NodeCreationError(
                message=get_message(
                    ExceptionMessageKey.TOOL_PARAMETERS_FROM_SCHEMA_FAILED_MSG
                ).format(reason=str(e)),
                notes=get_notes(ExceptionMessageKey.TOOL_PARAMETERS_TYPE_NOTES),
            ) from e

    elif isinstance(parameters, set):
        if not all(isinstance(x, param_type) for x in parameters):
            raise NodeCreationError(
                message=ExceptionMessageKey.PARAMETER_SET_CONTAINS_INVALID_TYPE_MSG,
                notes=ExceptionMessageKey.PARAMETER_SET_CONTAINS_INVALID_TYPE_NOTES,
            )

    return True


# ================================================================== END Tool init error ===========================================================


# ============================================================== START Tool Manifest Verification ===========================================================
def _check_manifest_params_exist_in_function(
    func_params: dict, manifest_params: dict
) -> None:
    """Check that all manifest parameters exist in function signature."""
    for param_name in manifest_params:
        if param_name not in func_params:
            raise NodeCreationError(
                message=f"Tool manifest parameter '{param_name}' does not exist in function signature.",
                notes=[
                    f"Function parameters are: {list(func_params.keys())}",
                    "Remove the extra parameter from the tool manifest or add it to the function signature.",
                ],
            )
        if (
            ParameterType.from_python_type(func_params[param_name].annotation)
            != manifest_params[param_name]
        ):
            raise NodeCreationError(
                message=f"Type mismatch for parameter '{param_name}': function expects '{ParameterType.from_python_type(func_params[param_name].annotation)}', but manifest specifies '{manifest_params[param_name]}'.",
                notes=[
                    "Ensure the parameter types in the tool manifest match the function signature.",
                    "Refer to the ParameterType enum for valid types.",
                ],
            )


def _check_required_params_in_manifest(
    func_params: dict, manifest_params: dict
) -> None:
    """Check that required function parameters are present in manifest."""
    for param_name, func_param in func_params.items():
        if func_param.default == inspect.Parameter.empty:  # Required parameter
            if param_name not in manifest_params:
                raise NodeCreationError(
                    message=f"Required function parameter '{param_name}' is missing from tool manifest.",
                    notes=[
                        "Add the missing parameter to the tool manifest.",
                        "All required function parameters must be included in the manifest.",
                    ],
                )
            if (
                ParameterType.from_python_type(func_params[param_name].annotation)
                != manifest_params[param_name]
            ):
                raise NodeCreationError(
                    message=f"Type mismatch for parameter '{param_name}': function expects '{ParameterType.from_python_type(func_params[param_name].annotation)}', but manifest specifies '{manifest_params[param_name]}'.",
                    notes=[
                        "Ensure the parameter types in the tool manifest match the function signature.",
                        "Refer to the ParameterType enum for valid types.",
                    ],
                )


def validate_tool_manifest_against_function(
    func: Callable, manifest_params: Iterable[Parameter] | None
) -> None:
    """
    Validate that tool manifest parameters are compatible with function signature.

    This checks that:
    1. Manifest parameter names match function parameter names
    2. Required function parameters are present in manifest (unless they have defaults)
    3. No extra parameters in manifest that don't exist in function
    4. Parameter types are broadly compatible considering type mapping

    Args:
        func: The function to validate against
        manifest_params: List of Parameter objects from ToolManifest, or None

    Raises:
        NodeCreationError: If validation fails
    """
    try:
        sig = inspect.signature(func)
    except ValueError:
        # For builtin functions, we can't validate - trust the user
        return

    # Get function parameters (excluding 'self' and 'cls' for methods)
    func_params = {}
    for param_name, param in sig.parameters.items():
        if param_name not in ("self", "cls"):
            func_params[param_name] = param

    if not manifest_params:
        if func_params:
            raise NodeCreationError(
                message="No Tool manifest parameters are provided but the function passed requires parameters",
                notes=[
                    f"Function parameters are: {list(func_params.keys())}",
                    "Please add the required parameters to the tool manifest.",
                ],
            )
        return
    else:
        if not func_params or func_params == {}:
            raise NodeCreationError(
                message="Tool manifest parameters are provided but the function passed does not accept any parameters",
                notes=[
                    "Please remove the parameters from the tool manifest.",
                ],
            )

    # Convert manifest parameters to dict for easier lookup
    manifest_param_dict = {p.name: p.param_type for p in manifest_params}

    # Perform all validation checks
    _check_manifest_params_exist_in_function(func_params, manifest_param_dict)
    _check_required_params_in_manifest(func_params, manifest_param_dict)


# ============================================================== END Tool Manifest Verification ===========================================================
