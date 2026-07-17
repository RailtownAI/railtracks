import asyncio
from copy import deepcopy
from typing import (
    Literal,
    Protocol,
    TypeVar,
    overload,
)

from pydantic import BaseModel

from railtracks.built_nodes.llm.model_invoker import ModelInvoker
from railtracks.built_nodes.llm.response import StringResponse, StructuredResponse
from railtracks.exceptions.errors import LLMError, NodeInvocationError
from railtracks.interaction._call import call
from railtracks.llm.content import ToolCall, ToolResponse
from railtracks.llm.history import MessageHistory
from railtracks.llm.message import (
    AssistantMessage,
    Message,
    SystemMessage,
    ToolMessage,
    UserMessage,
)
from railtracks.llm.response import Response
from railtracks.llm.tools.parameters._base import Parameter
from railtracks.llm.tools.tool import Tool
from railtracks.nodes.nodes import Node
from railtracks.validation.node_invocation.validation import check_message_history

_TStructured = TypeVar("_TStructured", bound=BaseModel)


class StringLLMInvoke(Protocol):
    async def __call__(
        self,
        user_input: MessageHistory | UserMessage | str | list[Message],
    ) -> StringResponse: ...


class StructuredLLMInvoke(Protocol[_TStructured]):
    async def __call__(
        self,
        user_input: MessageHistory | UserMessage | str | list[Message],
    ) -> StructuredResponse[_TStructured]: ...


@overload
def llm_invoke_factory(
    model_invoker: ModelInvoker,
    system_message: SystemMessage | None,
    *,
    tool_nodes: list[type[Node]] | None = None,
    schema: None = None,
) -> StringLLMInvoke: ...


@overload
def llm_invoke_factory(
    model_invoker: ModelInvoker,
    system_message: SystemMessage | None,
    *,
    tool_nodes: list[type[Node]] | None = None,
    schema: type[_TStructured],
) -> StructuredLLMInvoke[_TStructured]: ...


class LLMCallProtocol(Protocol):
    async def __call__(
        self,
        messages: MessageHistory,
        *,
        schema: type[BaseModel] | None = None,
        tools: list[Tool] | None = None,
    ) -> Response: ...


def llm_invoke_factory(
    model_invoker: ModelInvoker,
    system_message: SystemMessage | None,
    *,
    tool_nodes: list[type[Node]] | None = None,
    schema: type[_TStructured] | None = None,
):
    tools = [x.tool_info() for x in tool_nodes] if tool_nodes else None

    async def llm_invoke(
        user_input: MessageHistory | UserMessage | str | list[Message],
    ):
        message_history = prepare_message_history(system_message, user_input)

        while True:
            try:
                returned_mess = await model_invoker.invoke(
                    message_history, schema=schema, tools=tools
                )
            except NodeInvocationError:
                raise  # e.g. a guardrail block from a gate; surface as-is, don't mask
            except Exception as e:
                raise LLMError(
                    reason=f"Exception during model invoke: {repr(e)}",
                    message_history=message_history,
                )

            path = process_message(returned_mess, schema)

            if path == "Content":
                message_history.append(AssistantMessage(returned_mess.message.content))
                return prepare_string_response(message_history)
            elif path == "Structured":
                message_history.append(AssistantMessage(returned_mess.message.content))
                assert schema is not None
                return prepare_structured_response(message_history, schema)
            elif path == "Tool":
                await run_tools(returned_mess, message_history, tool_nodes or [])
                continue

    return llm_invoke


async def run_tools(
    response: Response,
    message_history: MessageHistory,
    tool_nodes: list[type[Node]],
):
    assert len(tool_nodes) > 0, "No tool nodes provided to run_tools"
    tool_calls = response.message.tool_calls

    hist_msg = AssistantMessage(content=tool_calls)

    raw = getattr(response.message, "raw_content", None)
    if raw is not None:
        hist_msg.raw_litellm_message = raw

    message_history.append(hist_msg)

    tool_messages = await invoke_tools(tool_calls, tool_nodes)

    message_history.extend(tool_messages)


async def invoke_tools(tool_calls: list[ToolCall], tool_nodes: list[type[Node]]):
    contracts = []

    for tool_call in tool_calls:
        contract = invoke_tool(tool_call, tool_nodes)
        contracts.append(contract)

    tool_results = await asyncio.gather(*contracts, return_exceptions=True)
    stringified_results = [
        (
            str(x)
            if not isinstance(x, Exception)
            else f"There was an error during tool execution: {repr(x)}"
        )
        for x in tool_results
    ]

    tool_ids = [tool_call.identifier for tool_call in tool_calls]
    tool_names = [tool_call.name for tool_call in tool_calls]

    tool_messages: list[ToolMessage] = []

    for tool_id, tool_name, result in zip(tool_ids, tool_names, stringified_results):
        tool_messages.append(
            ToolMessage(
                ToolResponse(
                    identifier=tool_id,
                    name=tool_name,
                    result=result,
                )
            )
        )

    return tool_messages


async def invoke_tool(tool_call: ToolCall, tool_nodes: list[type[Node]]):
    ToolNode = get_node_from_name(tool_call.name, tool_nodes)  # noqa: N806

    prepared_args = ToolNode.prepare_args(**tool_call.arguments)

    return await call(ToolNode, **prepared_args)


def get_node_from_name(tool_name: str, tool_nodes: list[type[Node]]) -> type[Node]:
    candidate_list = [x for x in tool_nodes if x.tool_info().name == tool_name]

    if len(candidate_list) == 0:
        raise RuntimeError(
            f"LLM called tool '{tool_name}' which was not found in the provided tool nodes {[x.tool_info().name for x in tool_nodes]}",
        )
    assert len(candidate_list) == 1, (
        f"Multiple tool nodes found with name '{tool_name}'. This should not happen, please ensure all tool nodes have unique names. Offending nodes: {candidate_list}"
    )

    return candidate_list[0]


def llm_prepare_called_as_tool_factory(
    params: list[Parameter],
):
    def prepare_called_as_tool(**kwargs):
        """
        Prepare a message history for a tool call with the given parameters.

        This method creates a coherent instruction message from tool parameters instead of
        multiple separate messages.

        Args:
            tool_parameters: Dictionary of parameter names to values
            tool_params: Iterable of Parameter objects defining the tool parameters

        Returns:
            MessageHistory object with a single UserMessage containing the formatted parameters
        """
        # If no parameters, return empty message history
        if not kwargs:
            return MessageHistory([])

        # Create a single, coherent instruction instead of multiple separate messages
        instruction_parts = [
            "You are being called as a tool with the following parameters:",
            "",
        ]

        for param in params:
            value = kwargs[param.name]
            # Format the parameter appropriately based on its type
            if param.param_type == "array" and isinstance(value, list):
                formatted_value = ", ".join(str(v) for v in value)
                instruction_parts.append(f"• {param.name}: {formatted_value}")
            elif param.param_type == "object" and isinstance(value, dict):
                # For objects, show key-value pairs
                formatted_value = "; ".join(f"{k}={v}" for k, v in value.items())
                instruction_parts.append(f"• {param.name}: {formatted_value}")
            else:
                instruction_parts.append(f"• {param.name}: {value}")

        instruction_parts.extend(
            ["", "Please execute your function based on these parameters."]
        )

        # Create a single UserMessage with the complete instruction
        return MessageHistory([UserMessage("\n".join(instruction_parts))])

    return prepare_called_as_tool


def process_message(
    response: Response,
    schema: type[_TStructured] | None,
) -> Literal["Tool", "Content", "Structured"]:
    tool_calls = response.message.tool_calls
    content = response.message.content

    if len(tool_calls) > 0:
        return "Tool"
    elif isinstance(content, str):
        return "Content"
    elif schema is not None and isinstance(content, schema):
        return "Structured"
    else:
        raise TypeError(
            f"Response content is of an unexpected type: {type(content)}. Expected str or {schema}."
        )


def prepare_message_history(
    system_message: SystemMessage | None,
    user_input: MessageHistory | UserMessage | str | list[Message],
) -> MessageHistory:
    message_history = create_message_history(user_input)

    check_message_history(
        message_history, system_message.content if system_message else None
    )

    append_system_message(message_history, system_message)

    return message_history


def create_message_history(
    user_input: MessageHistory | UserMessage | str | list[Message],
) -> MessageHistory:
    message_history: MessageHistory
    if isinstance(user_input, MessageHistory):
        message_history = user_input
    elif isinstance(user_input, UserMessage):
        message_history = MessageHistory([user_input])
    elif isinstance(user_input, str):
        message_history = MessageHistory([UserMessage(user_input)])
    elif isinstance(user_input, list):
        if not all(isinstance(msg, Message) for msg in user_input):
            raise ValueError("All items in the list must be instances of Message.")
        message_history = MessageHistory(user_input)
    else:
        raise ValueError(
            "Invalid input type for user_input. Must be MessageHistory, UserMessage, str, or list of Messages."
        )

    return deepcopy(message_history)


def append_system_message(
    message_history: MessageHistory, system_message: SystemMessage | None
):
    """Modifies the object in place"""
    if system_message:
        # Prepend the system message to the message history
        message_history.insert(0, system_message)


def prepare_structured_response(
    message_history: MessageHistory, schema: type[_TStructured]
) -> StructuredResponse[_TStructured]:
    last_message = message_history[-1]

    content = last_message.content

    assert isinstance(content, schema), (
        "Content of the last message must be a dict to be converted into a structured response"
    )

    return StructuredResponse(content=content, message_history=message_history)


def prepare_string_response(
    message_history: MessageHistory,
) -> StringResponse:
    last_message = message_history[-1]

    content = last_message.content

    assert isinstance(content, str), (
        "Content of the last message must be a string to be returned as is"
    )

    return StringResponse(content=content, message_history=message_history)
