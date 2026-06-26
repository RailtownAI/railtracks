import asyncio
from copy import deepcopy
from typing import (
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Literal,
    Protocol,
    TypeVar,
    overload,
)

from pydantic import BaseModel

from railtracks.built_nodes.concrete._llm_base import RequestDetails
from railtracks.built_nodes.concrete.response import StringResponse, StructuredResponse
from railtracks.exceptions.errors import LLMError
from railtracks.interaction._call import call
from railtracks.interaction.broadcast_ import broadcast
from railtracks.llm.content import ToolCall, ToolResponse
from railtracks.llm.history import MessageHistory
from railtracks.llm.message import (
    AssistantMessage,
    Message,
    SystemMessage,
    ToolMessage,
    UserMessage,
)
from railtracks.llm.model import ModelBase
from railtracks.llm.response import Response
from railtracks.llm.tools.parameters._base import Parameter
from railtracks.llm.tools.tool import Tool
from railtracks.middleware import Gate, MiddlewareChain
from railtracks.middleware.primitives import Wrapper, wrapper
from railtracks.nodes.nodes import Node
from railtracks.validation.node_invocation.validation import check_message_history

_TStructured = TypeVar("_TStructured", bound=BaseModel)

# A model source: a concrete model, or a no-arg factory resolved fresh on every
# call — the factory form lets a node pick its model at invocation time (e.g.
# from config or rt.context) instead of binding one at build time.
ModelSource = ModelBase[Literal[False]] | Callable[[], ModelBase[Literal[False]]]

# Streaming variant — model must have stream=True so achat/astructured/achat_with_tools
# return AsyncGenerator[str | Response, None] instead of Response.
StreamingModelSource = ModelBase[Literal[True]] | Callable[[], ModelBase[Literal[True]]]


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


class ModelInvoker:
    """
    Coordinates a single LLM model call through a :class:`MiddlewareChain`.

    The middleware operates around the *raw* model call, once per model
    round-trip (i.e. inside the tool-calling loop). The core callable takes
    ``(messages, schema, tools)`` and returns a :class:`Response`::

        wrappers
        └── entry gateways   (transform messages / schema / tools)
            └── inner_wrappers
                └── model.chat / structured / chat_with_tools
            └── (unwind)
        └── exit gateways    (transform the Response)
        └── (unwind)

    Accepts a :class:`MiddlewareChain` or a bare list of ``Wrapper`` / ``Gate``
    (see :meth:`MiddlewareChain.coerce`). The caller's input is never mutated — a
    fresh copy is taken so system gateways (e.g. context injection) stay
    independent per node.
    """

    def __init__(
        self,
        model: ModelSource | StreamingModelSource,
        middleware: MiddlewareChain[
            [MessageHistory, type[BaseModel] | None, list[Tool] | None], Response
        ]
        | None = None,
    ):
        self._get_model: Callable[[], ModelBase[Literal[False]] | ModelBase[Literal[True]]] = (
            model if callable(model) else lambda: model  # type: ignore[return-value]
        )
        self._middleware: MiddlewareChain[
            [MessageHistory, type[BaseModel] | None, list[Tool] | None], Response
        ] = MiddlewareChain.coerce(middleware)

    def register_sys_entry_gate(
        self,
        gw: Gate[
            [MessageHistory, type[BaseModel] | None, list[Tool] | None],
            tuple[tuple, dict[str, Any]],
        ],
    ) -> None:
        """Register a system entry gate around the model call (e.g. context injection)."""
        self._middleware.register_sys_entry_gate(gw)

    def register_sys_exit_gate(self, gw: Gate[[Response], Response]) -> None:
        """Register a system exit gate around the model call (e.g. logging)."""
        self._middleware.register_sys_exit_gate(gw)

    def register_sys_wrapper(
        self,
        w: Wrapper[
            [MessageHistory, type[BaseModel] | None, list[Tool] | None], Response
        ],
    ) -> None:
        """Register a system wrapper around the model call (e.g. logging)."""
        self._middleware.register_sys_outer_wrapper(w)

    async def invoke(
        self,
        messages: MessageHistory,
        *,
        schema: type[BaseModel] | None = None,
        tools: list[Tool] | None = None,
    ) -> Response:
        model = self._get_model()

        async def _core_llm_call(
            messages: MessageHistory,
            schema: type[BaseModel] | None,
            tools: list[Tool] | None,
        ) -> Response:
            if tools is not None and len(tools) > 0:
                return await asyncio.to_thread(
                    model.chat_with_tools, messages, tools=tools
                )
            elif schema is not None:
                return await asyncio.to_thread(
                    model.structured, messages, schema=schema
                )
            else:
                return await asyncio.to_thread(model.chat, messages)

        return await self._middleware.run(_core_llm_call, messages, schema, tools)

    async def invoke_stream(
        self,
        messages: MessageHistory,
        *,
        schema: type[BaseModel] | None = None,
        tools: list[Tool] | None = None,
    ) -> AsyncGenerator[str | Response, None]:
        """Run a streaming model call through the middleware chain.

        Entry gates transform the input; inner/outer wrappers forward chunks
        via their :meth:`~Wrapper.wrap_stream` pass-throughs; exit gates are
        applied to the terminal :class:`~railtracks.llm.response.Response` item
        before it is yielded.

        The model **must** have been constructed with ``stream=True``; a
        :class:`ValueError` is raised at call time otherwise.
        """
        model = self._get_model()
        if not model.stream:
            raise ValueError(
                "invoke_stream() requires a streaming model (stream=True). "
                "Use invoke() for non-streaming models."
            )

        async def _core_llm_stream(
            messages: MessageHistory,
            schema: type[BaseModel] | None,
            tools: list[Tool] | None,
        ) -> AsyncGenerator[str | Response, None]:
            if tools is not None and len(tools) > 0:
                gen = await model.achat_with_tools(messages, tools)
            elif schema is not None:
                gen = await model.astructured(messages, schema=schema)
            else:
                gen = await model.achat(messages)
            # gen is AsyncGenerator[str | Response, None] (model.stream=True)
            async for item in gen:  # type: ignore[union-attr]
                yield item

        async for item in self._middleware.run_stream(
            _core_llm_stream, messages, schema, tools
        ):
            yield item


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


class StringLLMStreamInvoke(Protocol):
    async def __call__(
        self,
        user_input: MessageHistory | UserMessage | str | list[Message],
    ) -> StringResponse: ...


class StructuredLLMStreamInvoke(Protocol[_TStructured]):
    async def __call__(
        self,
        user_input: MessageHistory | UserMessage | str | list[Message],
    ) -> StructuredResponse[_TStructured]: ...


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


@overload
def llm_stream_invoke_factory(
    model_invoker: ModelInvoker,
    system_message: SystemMessage | None,
    *,
    tool_nodes: list[type[Node]] | None = None,
    schema: None = None,
) -> StringLLMStreamInvoke: ...


@overload
def llm_stream_invoke_factory(
    model_invoker: ModelInvoker,
    system_message: SystemMessage | None,
    *,
    tool_nodes: list[type[Node]] | None = None,
    schema: type[_TStructured],
) -> StructuredLLMStreamInvoke[_TStructured]: ...


def llm_stream_invoke_factory(
    model_invoker: ModelInvoker,
    system_message: SystemMessage | None,
    *,
    tool_nodes: list[type[Node]] | None = None,
    schema: type[_TStructured] | None = None,
):
    """Build a streaming LLM invoke function.

    Identical contract to :func:`llm_invoke_factory` from the caller's
    perspective — accepts ``UserInput``, returns
    :class:`~railtracks.built_nodes.concrete.response.StringResponse` or
    :class:`~railtracks.built_nodes.concrete.response.StructuredResponse`.

    Internally the function streams the model response chunk-by-chunk,
    **auto-broadcasting** each ``str`` chunk via the pub/sub
    :func:`~railtracks.interaction.broadcast_.broadcast` helper so that any
    registered ``broadcast_callback`` receives real-time output.

    Tool-calling is supported: when the terminal
    :class:`~railtracks.llm.response.Response` indicates tool calls the stream
    pauses, tools execute, and a new streaming round-trip begins.
    """
    tools = [x.tool_info() for x in tool_nodes] if tool_nodes else None

    async def llm_stream_invoke(
        user_input: MessageHistory | UserMessage | str | list[Message],
    ):
        message_history = prepare_message_history(system_message, user_input)

        while True:
            accumulated: list[str] = []
            final_response: Response | None = None

            try:
                async for item in model_invoker.invoke_stream(
                    message_history, schema=schema, tools=tools
                ):
                    if isinstance(item, str):
                        accumulated.append(item)
                        await broadcast(item)
                    elif isinstance(item, Response):
                        final_response = item
            except Exception as e:
                raise LLMError(
                    reason=f"Exception during streaming model invoke: {repr(e)}",
                    message_history=message_history,
                )

            if final_response is None:
                raise LLMError(
                    reason="Streaming model invoke produced no Response",
                    message_history=message_history,
                )

            path = process_message(final_response, schema)

            if path == "Content":
                message_history.append(
                    AssistantMessage("".join(accumulated))
                )
                return prepare_string_response(message_history)
            elif path == "Structured":
                message_history.append(
                    AssistantMessage(final_response.message.content)
                )
                assert schema is not None
                return prepare_structured_response(message_history, schema)
            elif path == "Tool":
                await run_tools(final_response, message_history, tool_nodes or [])
                continue

    return llm_stream_invoke


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
    candidate_list = [x for x in tool_nodes if x.name() == tool_name]

    if len(candidate_list) == 0:
        # TODO: better error here
        raise TypeError(
            f"LLM called tool '{tool_name}' which was not found in the provided tool nodes.",
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


@wrapper
async def llm_observe(
    call: Callable[
        [MessageHistory, type[BaseModel] | None, list[Tool] | None], Awaitable[Response]
    ],
    message_history: MessageHistory,
    schema: type[BaseModel] | None,
    tools: list[Tool] | None,
) -> Response:
    prev_message_history = deepcopy(message_history)
    response: Response = await call(message_history, schema, tools)
    _ = RequestDetails(
        message_input=prev_message_history,
        output=response.message,
        model_name=response.message_info.model_name,
        model_provider=None,  # TODO: implement parsing logic here
        input_tokens=response.message_info.input_tokens,
        output_tokens=response.message_info.output_tokens,
        total_cost=response.message_info.total_cost,
        system_fingerprint=response.message_info.system_fingerprint,
        latency=response.message_info.latency,
    )
    return response
