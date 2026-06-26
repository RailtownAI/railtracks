from typing import Iterable, Literal, Type, TypeVar, overload

from pydantic import BaseModel

from railtracks.built_nodes.concrete import (
    RTFunction,
)
from railtracks.built_nodes.concrete.response import StringResponse, StructuredResponse
from railtracks.built_nodes.llm_helpers import ModelSource, StreamingModelSource
from railtracks.llm.message import SystemMessage
from railtracks.llm.tools.parameters._base import Parameter
from railtracks.middleware import MiddlewareChain
from railtracks.nodes.manifest import ToolManifest
from railtracks.nodes.nodes import Node
from railtracks.nodes.utils import extract_node_from_function

from .._node_builder import NodeBuilder, UserInput

_TBaseModel = TypeVar("_TBaseModel", bound=BaseModel)


def _unpack_tool_nodes(
    tool_nodes: Iterable[Type[Node] | RTFunction] | None,
) -> set[Type[Node]] | None:
    if tool_nodes is None:
        return None
    unpacked: set[Type[Node]] = set()
    for node in tool_nodes:
        if isinstance(node, RTFunction):
            unpacked.add(extract_node_from_function(node))
        else:
            assert issubclass(node, Node), f"Expected {node} to be a subclass of Node"
            unpacked.add(node)
    return unpacked


def _build_dynamic_agent(
    *,
    unpacked_tool_nodes: set[Type[Node]] | None,
    output_schema: Type[_TBaseModel] | None,
    name: str | None,
    llm: ModelSource | StreamingModelSource,
    system_message: SystemMessage | str | None,
    tool_details: str | None,
    tool_params: list[Parameter] | None,
    middleware: MiddlewareChain | list | None = None,
    model_middleware: MiddlewareChain | list | None = None,
    context_injection: bool = True,
    stream: bool = False,
):
    resolved_system = (
        SystemMessage(content=system_message)
        if isinstance(system_message, str)
        else system_message
    )

    if output_schema is None:
        nb = NodeBuilder.llm(
            name=name if name is not None else "LLM Agent",
            model=llm,
            system_message=resolved_system,
            connected_nodes=unpacked_tool_nodes,
            tool_details=tool_details,
            tool_params=tool_params,
            middleware=middleware,
            model_middleware=model_middleware,
            context_injection=context_injection,
            stream=stream,
        )
    else:
        nb = NodeBuilder.llm(
            name=name if name is not None else "LLM Agent",
            model=llm,
            system_message=resolved_system,
            schema=output_schema,
            connected_nodes=unpacked_tool_nodes,
            tool_details=tool_details,
            tool_params=tool_params,
            middleware=middleware,
            model_middleware=model_middleware,
            context_injection=context_injection,
            stream=stream,
        )

    return nb.build()


# --- Non-streaming overloads ---


@overload
def agent_node(
    name: str | None = None,
    *,
    tool_nodes: Iterable[Type[Node] | RTFunction] | None = None,
    output_schema: None = None,
    llm: ModelSource,
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
    middleware: MiddlewareChain | list | None = None,
    model_middleware: MiddlewareChain | list | None = None,
    context_injection: bool = True,
    stream: Literal[False] = ...,
) -> type[Node[[UserInput], StringResponse]]: ...


@overload
def agent_node(
    name: str | None = None,
    *,
    tool_nodes: Iterable[Type[Node] | RTFunction] | None = None,
    output_schema: Type[_TBaseModel],
    llm: ModelSource,
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
    middleware: MiddlewareChain | list | None = None,
    model_middleware: MiddlewareChain | list | None = None,
    context_injection: bool = True,
    stream: Literal[False] = ...,
) -> type[Node[[UserInput], StructuredResponse[_TBaseModel]]]: ...


# --- Streaming overloads (llm must be a StreamingModelSource) ---


@overload
def agent_node(
    name: str | None = None,
    *,
    tool_nodes: Iterable[Type[Node] | RTFunction] | None = None,
    output_schema: None = None,
    llm: StreamingModelSource,
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
    middleware: MiddlewareChain | list | None = None,
    model_middleware: MiddlewareChain | list | None = None,
    context_injection: bool = True,
    stream: Literal[True],
) -> type[Node[[UserInput], StringResponse]]: ...


@overload
def agent_node(
    name: str | None = None,
    *,
    tool_nodes: Iterable[Type[Node] | RTFunction] | None = None,
    output_schema: Type[_TBaseModel],
    llm: StreamingModelSource,
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
    middleware: MiddlewareChain | list | None = None,
    model_middleware: MiddlewareChain | list | None = None,
    context_injection: bool = True,
    stream: Literal[True],
) -> type[Node[[UserInput], StructuredResponse[_TBaseModel]]]: ...


def agent_node(
    name: str | None = None,
    *,
    tool_nodes: Iterable[Type[Node] | RTFunction] | None = None,
    output_schema: Type[_TBaseModel] | None = None,
    llm: ModelSource | StreamingModelSource,
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
    middleware: MiddlewareChain | list | None = None,
    model_middleware: MiddlewareChain | list | None = None,
    context_injection: bool = True,
    stream: bool = False,
):
    """
    Dynamically creates an agent based on the provided parameters.

    Args:
        name (str | None): The name of the agent. If none the default will be used.
        tool_nodes (Iterable[Type[Node] | RTFunction] | None): If your agent has access to tools, what does it have access to?
        output_schema (Type[_TBaseModel] | None): If your agent should return a structured output, what is the output_schema?
        llm (ModelBase | Callable[[], ModelBase]): The LLM model to use, or a no-arg
            factory resolved fresh on every model call. For streaming, pass a model
            constructed with ``stream=True`` and set ``stream=True`` here too.
        system_message (SystemMessage | str | None): System message for the agent.
        manifest (ToolManifest | None): If you want to use this as a tool in other agents you can pass in a ToolManifest.
        middleware (MiddlewareChain | list | None): Middleware applied around the agent's node boundary
            (user_input -> Response). Accepts a MiddlewareChain or a bare list of Wrapper/Gate.
        model_middleware (MiddlewareChain | list | None): Middleware applied around each raw model call
            (messages/schema/tools -> Response), inside the tool-calling loop. Accepts a MiddlewareChain or a
            bare list of Wrapper/Gate.
        context_injection (bool): Whether to inject rt.context variables into prompt templates for this node.
            Defaults to True. Set to False to disable context injection for this specific agent regardless
            of the session-level prompt_injection setting. Can also be controlled at the session level via
            rt.Session(prompt_injection=False) or per-message via message.inject_prompt = False.
        stream (bool): Enable the streaming execution path. When ``True`` the node still returns a
            ``StringResponse`` / ``StructuredResponse`` (unchanged from the non-streaming API), but
            each token chunk is broadcast in real time to the ``broadcast_callback`` registered on
            ``Flow`` or ``Session``. Requires ``llm`` to be constructed with ``stream=True``.
            Defaults to ``False``.
    """
    unpacked_tool_nodes = _unpack_tool_nodes(tool_nodes)

    # See issue (___) this logic should be migrated soon.
    if manifest is not None:
        tool_details = manifest.description
        tool_params = manifest.parameters
    else:
        tool_details = None
        tool_params = None

    agent = _build_dynamic_agent(
        unpacked_tool_nodes=unpacked_tool_nodes,
        output_schema=output_schema,
        name=name,
        llm=llm,
        system_message=system_message,
        tool_details=tool_details,
        tool_params=tool_params,
        middleware=middleware,
        model_middleware=model_middleware,
        context_injection=context_injection,
        stream=stream,
    )

    return agent
