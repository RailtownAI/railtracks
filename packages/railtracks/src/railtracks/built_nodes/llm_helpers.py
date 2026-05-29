
import asyncio
from copy import deepcopy
from typing import Any, Callable, Coroutine, Generic, Literal, Protocol, TypeVar, cast, overload
from urllib import response
from urllib import response

from pydantic import BaseModel
from railtracks.built_nodes.concrete.response import StringResponse, StructuredResponse
from railtracks.exceptions.errors import LLMError
from railtracks.llm.history import MessageHistory
from railtracks.llm.message import SystemMessage, UserMessage, Message
from railtracks.llm.model import ModelBase
from railtracks.llm.response import Response
from railtracks.llm.tools.parameters._base import Parameter
from railtracks.llm.tools.tool import Tool
from railtracks.nodes.nodes import Node
from railtracks.nodes.wrappers import Wrapper
from railtracks.validation.node_invocation.validation import check_message_history

_TStructured = TypeVar("_TStructured", bound=BaseModel)
_TStream = TypeVar("_TStream", Literal[True], Literal[False])
_TResponse = TypeVar("_TResponse")

_TResponseCo = TypeVar("_TResponseCo", covariant=True)


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


class GatewayCall(Protocol[_TResponseCo]):
    """The core model call as seen by gateway middleware."""
    def __call__(
        self,
        messages: MessageHistory,
        schema: type[BaseModel] | None,
        tools: list[Tool] | None,
    ) -> _TResponseCo: ...


class GatewayWrapper(Protocol[_TResponse]):
    """Takes a GatewayCall and returns a GatewayCall with the same signature.
    Used for retry logic, fallback models, logging, etc."""
    def __call__(
        self,
        fn: GatewayCall[_TResponse],
    ) -> GatewayCall[_TResponse]: ...


class GatewayPreMapper(Protocol):
    """Transforms inputs before the model call (e.g. message injection, schema rewriting)."""
    def __call__(
        self,
        messages: MessageHistory,
        schema: type[BaseModel] | None,
        tools: list[Tool] | None,
    ) -> tuple[MessageHistory, type[BaseModel] | None, list[Tool] | None]: ...


class GatewayPostMapper(Protocol[_TResponse]):
    """Transforms the model response (e.g. normalisation, redaction)."""
    def __call__(self, response: _TResponse) -> _TResponse: ...


class ModelGateway(Generic[_TStructured]):
    def __init__(
        self,
        model: ModelBase[Literal[False]] | Callable[[], ModelBase[Literal[False]]],
        wrappers: list[GatewayWrapper[Response]] | None = None,
        pre_mappers: list[GatewayPreMapper] | None = None,
        post_mappers: list[GatewayPostMapper[Response]] | None = None,
    ):
        self._get_model = model if callable(model) else lambda: model
        self._wrappers = wrappers or []
        self._pre_mapping = pre_mappers or []
        self._post_mapping = post_mappers or []

    def invoke(
        self, 
        messages: MessageHistory,
        *,
        schema: type[BaseModel] | None = None,
        tools: list[Tool] | None = None
    ):
        model = self._get_model()

        def _core_llm_call(messages: MessageHistory, schema: type[BaseModel] | None, tools: list[Tool] | None):
            for pre_map in self._pre_mapping:
                messages, schema, tools = pre_map(messages, schema, tools)

            if tools is not None and len(tools) > 0:
                response = model.chat_with_tools(messages, tools=tools)
            elif schema is not None:
                response = model.structured(messages, schema=schema)
            else:
                response = model.chat(messages)

            for post_map in self._post_mapping:
                response = post_map(response)

            return response
            
        llm_function = _core_llm_call

        for wrapper in self._wrappers:
            llm_function = wrapper(llm_function)

        response = llm_function(messages, schema, tools)

    
        return response



@overload
def llm_invoke_factory(
    model_gateway: ModelGateway,
    system_message: SystemMessage | None,
    tool_nodes: list[type[Node]] | None = None,
    schema: None = None,
) -> StringLLMInvoke: ...

@overload
def llm_invoke_factory(
    model_gateway: ModelGateway[_TStructured],
    system_message: SystemMessage | None,
    tool_nodes: list[type[Node]] | None = None,
    schema: type[_TStructured] = ...,
) -> StructuredLLMInvoke[_TStructured]: ...

def llm_invoke_factory(
    model_gateway: ModelGateway[_TStructured],
    system_message: SystemMessage | None,
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
                returned_mess = await asyncio.to_thread(model_gateway.invoke, message_history, schema=schema, tools=tools)
            except Exception as e:
                raise LLMError(
                    reason=f"Exception during model gateway invoke: {repr(e)}",
                    message_history=message_history,
                )

            path = process_message(returned_mess, schema)

            if path == "Content":
                return prepare_string_response(message_history)
            elif path == "Structured":
                assert schema is not None
                return prepare_structured_response(message_history, schema)
            elif path == "Tool":
                # TODO: handle tool calls here by running them and appending them to the results
                pass

        
    return llm_invoke

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

    check_message_history(message_history, system_message.content if system_message else None)

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
        raise ValueError("Invalid input type for user_input. Must be MessageHistory, UserMessage, str, or list of Messages.") 
        
    return deepcopy(message_history)

def append_system_message(
    message_history: MessageHistory,
    system_message: SystemMessage | None
):
    """Modifies the object in place"""
    if system_message:
        # Prepend the system message to the message history
        message_history.insert(0, system_message)
    

def prepare_structured_response(
        message_history: MessageHistory,
        schema: type[_TStructured]
    ) -> StructuredResponse[_TStructured]:
        last_message = message_history[-1]

        content = last_message.content

        assert isinstance(content, schema), "Content of the last message must be a dict to be converted into a structured response"

        return StructuredResponse(
            content=content,
            message_history=message_history
        )
    
def prepare_string_response(
        message_history: MessageHistory,
    ) -> StringResponse:
        last_message = message_history[-1]

        content = last_message.content

        assert isinstance(content, str), "Content of the last message must be a string to be returned as is"

        return StringResponse(
            content=content,
            message_history=message_history
        )