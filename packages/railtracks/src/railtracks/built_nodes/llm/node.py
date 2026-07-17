from typing import Iterable, Literal, Type, TypeVar, overload

from pydantic import BaseModel

from railtracks.built_nodes._types import ModelSource
from railtracks.built_nodes.function.base import (
    RTFunction,
)
from railtracks.built_nodes.llm.middleware.core import ModelMiddleware
from railtracks.built_nodes.llm.response import StringResponse, StructuredResponse
from railtracks.llm.message import SystemMessage
from railtracks.llm.tools.parameters._base import Parameter
from railtracks.middleware.core import Middleware
from railtracks.nodes.manifest import ToolManifest
from railtracks.nodes.nodes import Node
from railtracks.nodes.utils import extract_node_from_function

from .node_builder import LLMNodeBuilder, UserInput

_TBaseModel = TypeVar("_TBaseModel", bound=BaseModel)
_TStream = TypeVar("_TStream", Literal[True], Literal[False])
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
    context_injection: bool = True,
):
    resolved_system = (
        SystemMessage(content=system_message)
        if isinstance(system_message, str)
        else system_message
    )

    if output_schema is None:
        nb = LLMNodeBuilder.llm(
            name=name if name is not None else "LLM Agent",
            model=llm,
            system_message=resolved_system,
            connected_nodes=unpacked_tool_nodes,
            tool_details=tool_details,
            tool_params=tool_params,
            middleware=middleware,
            model_middleware=model_middleware,
            context_injection=context_injection,
        )
    else:
        nb = LLMNodeBuilder.llm(
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
        )

    return nb.build()


# --- agent_node overloads (string vs structured output) ---


@overload
def agent_node(
    name: str | None = None,
    *,
<<<<<<< HEAD
    tool_nodes: Iterable[Type[Node] | Callable | RTFunction],
=======
    tool_nodes: Iterable[Type[Node] | RTFunction] | None = None,
    output_schema: None = None,
    llm: ModelSource,
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
    middleware: list[Middleware[[UserInput], StringResponse]] | None = None,
    model_middleware: list[ModelMiddleware] | None = None,
    context_injection: bool = True,
) -> type[Node[[UserInput], StringResponse]]: ...


@overload
def agent_node(
    name: str | None = None,
    *,
    tool_nodes: Iterable[Type[Node] | RTFunction] | None = None,
>>>>>>> feature-branch-node-add-on
    output_schema: Type[_TBaseModel],
    llm: ModelSource,
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
<<<<<<< HEAD
    guardrails: None = None,
) -> Type[StructuredToolCallLLM[_TBaseModel]]:
    pass


@overload
def agent_node(
    name: str | None = None,
    *,
    tool_nodes: Iterable[Type[Node] | Callable | RTFunction],
    llm: ModelBase[Literal[False]] | None = None,
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
    guardrails: None = None,
) -> Type[ToolCallLLM]:
    pass


@overload
def agent_node(
    name: str | None = None,
    *,
    tool_nodes: Iterable[Type[Node] | Callable | RTFunction],
    llm: ModelBase[Literal[True]],
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
    guardrails: None = None,
) -> Type[StreamingToolCallLLM]:
    pass


# --- Tool-calling overloads (with guardrails) ---


@overload
def agent_node(
    name: str | None = None,
    *,
    tool_nodes: Iterable[Type[Node] | Callable | RTFunction],
    output_schema: Type[_TBaseModel],
    llm: ModelBase[Literal[False]] | None = None,
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
    guardrails: Guard,
) -> Type[GuardedStructuredToolCallLLM[_TBaseModel]]:
    pass


@overload
def agent_node(
    name: str | None = None,
    *,
    tool_nodes: Iterable[Type[Node] | Callable | RTFunction],
    llm: ModelBase[Literal[False]] | None = None,
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
    guardrails: Guard,
) -> Type[GuardedToolCallLLM]:
    pass


@overload
def agent_node(
    name: str | None = None,
    *,
    tool_nodes: Iterable[Type[Node] | Callable | RTFunction],
    llm: ModelBase[Literal[True]],
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
    guardrails: Guard,
) -> Type[GuardedStreamingToolCallLLM]:
    pass


# --- Structured overloads (no guardrails) ---


@overload
def agent_node(
    name: str | None = None,
    *,
    output_schema: Type[_TBaseModel],
    llm: ModelBase[Literal[False]] | None = None,
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
    guardrails: None = None,
) -> Type[StructuredLLM[_TBaseModel]]:
    pass


@overload
def agent_node(
    name: str | None = None,
    *,
    output_schema: Type[_TBaseModel],
    llm: ModelBase[Literal[True]],
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
    guardrails: None = None,
) -> Type[StreamingStructuredLLM[_TBaseModel]]:
    pass


# --- Structured overloads (with guardrails) ---


@overload
def agent_node(
    name: str | None = None,
    *,
    output_schema: Type[_TBaseModel],
    llm: ModelBase[Literal[False]] | None = None,
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
    guardrails: Guard,
) -> Type[GuardedStructuredLLM[_TBaseModel]]:
    pass


@overload
def agent_node(
    name: str | None = None,
    *,
    output_schema: Type[_TBaseModel],
    llm: ModelBase[Literal[True]],
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
    guardrails: Guard,
) -> Type[GuardedStreamingStructuredLLM[_TBaseModel]]:
    pass


# --- Terminal overloads ---


@overload
def agent_node(
    name: str | None = None,
    *,
    llm: ModelBase[Literal[False]] | None = None,
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
    guardrails: None = None,
) -> Type[TerminalLLM]:
    pass


@overload
def agent_node(
    name: str | None = None,
    *,
    llm: ModelBase[Literal[False]] | None = None,
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
    guardrails: Guard,
) -> Type[GuardedTerminalLLM]:
    pass


@overload
def agent_node(
    name: str | None = None,
    *,
    llm: ModelBase[Literal[True]],
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
    guardrails: None = None,
) -> Type[StreamingTerminalLLM]:
    pass


@overload
def agent_node(
    name: str | None = None,
    *,
    llm: ModelBase[Literal[True]],
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
    guardrails: Guard,
) -> Type[GuardedStreamingTerminalLLM]:
    pass
=======
    middleware: list[Middleware[[UserInput], StructuredResponse[_TBaseModel]]]
    | None = None,
    model_middleware: list[ModelMiddleware] | None = None,
    context_injection: bool = True,
) -> type[Node[[UserInput], StructuredResponse[_TBaseModel]]]: ...
>>>>>>> feature-branch-node-add-on


def agent_node(
    name: str | None = None,
    *,
<<<<<<< HEAD
    tool_nodes: Iterable[Type[Node] | Callable | RTFunction] | None = None,
=======
    tool_nodes: Iterable[Type[Node] | RTFunction] | None = None,
>>>>>>> feature-branch-node-add-on
    output_schema: Type[_TBaseModel] | None = None,
    llm: ModelSource,
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
    middleware: list[
        Middleware[[UserInput], StructuredResponse[_TBaseModel] | StringResponse]
    ]
    | None = None,
    model_middleware: list[ModelMiddleware] | None = None,
    context_injection: bool = True,
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
            (messages/schema/tools -> Response), inside the tool-calling loop. LLM guardrails
            (e.g. `InputGuard`/`OutputGuard` subclasses) are plain entries in this list — there is
            no separate guardrails slot, so list order is exactly execution order and is fully
            caller-controlled.
        context_injection (bool): Whether to inject rt.context variables into prompt templates for this node.
            Defaults to True. Set to False to disable context injection for this specific agent regardless
            of the session-level prompt_injection setting. Can also be controlled at the session level via
            rt.Session(prompt_injection=False) or per-message via message.inject_prompt = False.
    """
    unpacked_tool_nodes = _unpack_tool_nodes(tool_nodes)

    # See issue (___) this logic should be migrated soon.
    if manifest is not None:
        tool_details = manifest.description
        tool_params = manifest.parameters
    else:
        tool_details = None
        tool_params = None

    return _build_dynamic_agent(
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
    )

    return agent
