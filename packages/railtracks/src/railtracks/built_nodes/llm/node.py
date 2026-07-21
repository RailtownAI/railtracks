from typing import Iterable, Type, TypeVar, overload

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
    middleware: list[Middleware[[UserInput], StructuredResponse[_TBaseModel]]]
    | None = None,
    model_middleware: list[ModelMiddleware] | None = None,
) -> type[Node[[UserInput], StructuredResponse[_TBaseModel]]]: ...


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
):# -> type[Node[Callable[[UserInput], Any], StringResponse]] | Any:# -> type[Node[Callable[[UserInput], Any], StringResponse]] | Any:# -> type[Node[Callable[[UserInput], Any], StringResponse]] | Any:# -> type[Node[Callable[[UserInput], Any], StringResponse]] | Any:# -> type[Node[Callable[[UserInput], Any], StringResponse]] | Any:
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
    )

    return agent
