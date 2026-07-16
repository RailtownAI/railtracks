from typing import Iterable, Type, TypeVar, overload

from pydantic import BaseModel

from railtracks.built_nodes._types import ModelSource
from railtracks.built_nodes.concrete import (
    RTFunction,
)
from railtracks.built_nodes.concrete.response import StringResponse, StructuredResponse
from railtracks.built_nodes.llm.middleware.core import ModelMiddleware
from railtracks.guardrails.core import Guard
from railtracks.llm.message import SystemMessage
from railtracks.llm.tools.parameters._base import Parameter
from railtracks.middleware.core import Middleware
from railtracks.nodes.manifest import ToolManifest
from railtracks.nodes.nodes import Node
from railtracks.nodes.utils import extract_node_from_function

from .._node_builder import NodeBuilder, UserInput

_TBaseModel = TypeVar("_TBaseModel", bound=BaseModel)
_R = TypeVar("_R", bound=StructuredResponse | StringResponse)


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
    llm: ModelSource,
    system_message: SystemMessage | str | None,
    tool_details: str | None,
    tool_params: list[Parameter] | None,
    middleware: list[Middleware[[UserInput], _R]] | None = None,
    model_middleware: list[ModelMiddleware] | None = None,
    guardrails: Guard | None = None,
    context_injection: bool = True,
    stream_channel: str = "default",
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
            guardrails=guardrails,
            context_injection=context_injection,
            stream_channel=stream_channel,
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
            guardrails=guardrails,
            context_injection=context_injection,
            stream_channel=stream_channel,
        )

    return nb.build()


# --- agent_node overloads (string vs structured output) ---


@overload
def agent_node(
    name: str | None = None,
    *,
    tool_nodes: Iterable[Type[Node] | RTFunction] | None = None,
    output_schema: None = None,
    llm: ModelSource,
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
    middleware: list[Middleware[[UserInput], StringResponse]] | None = None,
    model_middleware: list[ModelMiddleware] | None = None,
    guardrails: Guard | None = None,
    context_injection: bool = True,
    stream_channel: str = "default",
    # note: the parameter spec is `...` (not `[UserInput]`) so both the canonical keyword
    # style `rt.call(agent, user_input=...)` and the positional style type-check.
) -> type[Node[..., StringResponse]]: ...


@overload
def agent_node(
    name: str | None = None,
    *,
    tool_nodes: Iterable[Type[Node] | RTFunction] | None = None,
    output_schema: Type[_TBaseModel],
    llm: ModelSource,
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
    middleware: list[Middleware[[UserInput], StructuredResponse[_TBaseModel]]]
    | None = None,
    model_middleware: list[ModelMiddleware] | None = None,
    guardrails: Guard | None = None,
    context_injection: bool = True,
    stream_channel: str = "default",
    # note: the parameter spec is `...` (not `[UserInput]`) so both the canonical keyword
    # style `rt.call(agent, user_input=...)` and the positional style type-check.
) -> type[Node[..., StructuredResponse[_TBaseModel]]]: ...


def agent_node(
    name: str | None = None,
    *,
    tool_nodes: Iterable[Type[Node] | RTFunction] | None = None,
    output_schema: Type[_TBaseModel] | None = None,
    llm: ModelSource,
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
    middleware: list[
        Middleware[[UserInput], StructuredResponse[_TBaseModel] | StringResponse]
    ]
    | None = None,
    model_middleware: list[ModelMiddleware] | None = None,
    guardrails: Guard | None = None,
    context_injection: bool = True,
    stream_channel: str = "default",
):
    """
    Dynamically creates an agent based on the provided parameters.

    Args:
        name (str | None): The name of the agent. If none the default will be used.
        tool_nodes (Iterable[Type[Node] | RTFunction] | None): If your agent has access to tools, what does it have access to?
        output_schema (Type[_TBaseModel] | None): If your agent should return a structured output, what is the output_schema?
        llm (ModelBase | Callable[[], ModelBase]): The LLM model to use, or a no-arg
            factory resolved fresh on every model call (lets the agent pick its model
            at invocation time, e.g. from config or rt.context).
        system_message (SystemMessage | str | None): System message for the agent.
        manifest (ToolManifest | None): If you want to use this as a tool in other agents you can pass in a ToolManifest.
        middleware (list[Middleware] | None): Middleware applied around the agent's node boundary
            (user_input -> Response).
        model_middleware (list[Middleware] | None): Middleware applied around each raw model call
            (messages/schema/tools -> Response), inside the tool-calling loop.
        guardrails (Guard | None): Input/output LLM guardrails to enforce around the model call. Input rails
            run as the last check before the model (after context injection and any model_middleware); output
            rails run on the final reply as the last word. Attached as fixed, non-reorderable system middleware.
        context_injection (bool): Whether to inject rt.context variables into prompt templates for this node.
            Defaults to True. Set to False to disable context injection for this specific agent regardless
            of the session-level prompt_injection setting. Can also be controlled at the session level via
            rt.Session(prompt_injection=False) or per-message via message.inject_prompt = False.
        stream_channel (str): The named channel this agent's streamed tokens are broadcast on
            when a run streams (see `rt.astream` / `stream_callback`). Defaults to "default".
            Give different agents in one flow distinct channels to route their tokens to
            different consumers (e.g. `stream_callback={"writer": fn1, "critic": fn2}` or
            `stream.on_channel("writer")`). Note each round of a tool-calling loop is one
            production on this channel.
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
        guardrails=guardrails,
        context_injection=context_injection,
        stream_channel=stream_channel,
    )

    return agent
