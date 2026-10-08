"""How an agent presents itself, and reads its input, when another agent calls it as a tool."""

from typing import Callable

from railtracks.exceptions.errors import NodeCreationError
from railtracks.exceptions.messages.exception_messages import (
    ExceptionMessageKey,
    get_message,
    get_notes,
)
from railtracks.llm import MessageHistory, Parameter, SystemMessage, Tool
from railtracks.llm.tools.tool import to_tool_name
from railtracks.validation.node_creation.validation import (
    _check_duplicate_param_names,
    _check_manifest_description,
    _check_tool_params_and_details,
)

from .llm_helpers import llm_prepare_called_as_tool_factory

REQUEST_PARAMETER_NAME = "request"
REQUEST_PARAMETER_DESCRIPTION = (
    "The task for this agent, in plain language. Include every detail it needs, "
    "because it cannot see your conversation."
)
DEFAULT_DESCRIPTION_TEMPLATE = (
    'Hands a task to the sub-agent "{agent_name}" and returns its final reply. '
    "The sub-agent follows these instructions:\n{instructions}"
)

AgentToolArguments = dict[str, str | MessageHistory]


def agent_tool_info(
    agent_name: str,
    system_message: SystemMessage | None,
    tool_details: str | None,
    tool_params: list[Parameter] | None,
) -> Callable[[], Tool]:
    """
    Build an agent's `tool_info`, which is what a calling agent sees of it.

    A manifest's description and parameters are used as given. Without a manifest, the
    description is built from the agent's system message. When there are no parameters,
    the tool takes a single required string, `request`.

    Args:
        agent_name: The name of the agent.
        system_message: The agent's configured system message, if it has one.
        tool_details: The manifest's description, or None when the agent has no manifest.
        tool_params: The manifest's parameters, if any.

    Returns:
        A callable returning the agent's tool. When the agent has neither a manifest nor a
        system message, the callable raises NodeCreationError instead, so the agent only
        fails once it is used as a tool.

    Raises:
        NodeCreationError: If the manifest's description is blank, or its parameters are
            invalid.
    """
    _check_tool_params_and_details(tool_params, tool_details)

    if tool_details is None:
        tool_details = _describe_from_system_message(agent_name, system_message)
        if tool_details is None:
            return lambda: _raise_missing_description(agent_name)
    else:
        _check_manifest_description(tool_details, agent_name)

    _check_duplicate_param_names(tool_params or [])
    tool = Tool(
        name=to_tool_name(agent_name),
        detail=tool_details,
        parameters=tool_params or [request_parameter()],
    )
    return lambda: tool


def agent_tool_arguments(
    tool_params: list[Parameter] | None,
) -> Callable[..., AgentToolArguments]:
    """
    Build an agent's `prepare_args`, which turns a tool call into the agent's input.

    Args:
        tool_params: The manifest's parameters, if any.

    Returns:
        A callable taking the tool call's arguments. With no manifest parameters, it passes
        `request` through as the agent's user input. Otherwise it formats the arguments into
        a single instruction message.
    """
    if not tool_params:
        return _prepare_request

    prepare_history = llm_prepare_called_as_tool_factory(tool_params)
    return lambda **kwargs: {"user_input": prepare_history(**kwargs)}


def request_parameter() -> Parameter:
    """
    Build the parameter an agent takes as a tool when its manifest declares none.

    Returns:
        A new required string parameter named `request`.
    """
    return Parameter(
        name=REQUEST_PARAMETER_NAME,
        description=REQUEST_PARAMETER_DESCRIPTION,
        param_type="string",
    )


def _prepare_request(**kwargs: object) -> AgentToolArguments:
    """
    Pass a tool call's `request` argument to the agent as its user input.

    Args:
        **kwargs: The arguments of the tool call.

    Returns:
        The agent's invocation arguments.

    Raises:
        TypeError: If the tool call has no `request` argument.
    """
    if REQUEST_PARAMETER_NAME not in kwargs:
        raise TypeError(f"Missing required tool argument: '{REQUEST_PARAMETER_NAME}'.")
    return {"user_input": str(kwargs[REQUEST_PARAMETER_NAME])}


def _describe_from_system_message(
    agent_name: str, system_message: SystemMessage | None
) -> str | None:
    """
    Describe an agent to a calling agent using its system message.

    Args:
        agent_name: The name of the agent.
        system_message: The agent's configured system message, if it has one.

    Returns:
        The description, or None if the agent has no system message or it is blank.
    """
    if system_message is None or not system_message.content.strip():
        return None

    return DEFAULT_DESCRIPTION_TEMPLATE.format(
        agent_name=agent_name, instructions=system_message.content
    )


def _raise_missing_description(agent_name: str) -> Tool:
    """
    Fail the `tool_info` of an agent that has nothing to describe it with.

    Args:
        agent_name: The name of the agent.

    Raises:
        NodeCreationError: Always, explaining how to make the agent usable as a tool.
    """
    raise NodeCreationError(
        get_message(ExceptionMessageKey.AGENT_TOOL_DESCRIPTION_MISSING_MSG).format(
            agent_name=agent_name
        ),
        notes=get_notes(ExceptionMessageKey.AGENT_TOOL_DESCRIPTION_MISSING_NOTES),
    )
