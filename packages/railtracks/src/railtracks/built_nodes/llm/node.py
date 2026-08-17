from typing import Callable, Iterable, ParamSpec, Type, TypeVar, cast, overload

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
_P = ParamSpec("_P")


def _user_input_shape(user_input: UserInput) -> object:
    """Never called -- exists purely so pyright infers `_P` (below) from a real,
    named parameter instead of the positional-only literal-list form `[UserInput]`.
    A ParamSpec solved this way (via a defaulted argument on a plain function) keeps
    the parameter name through `*args: _P.args, **kwargs: _P.kwargs` wherever `_P` is
    later threaded -- e.g. in `rt.call`/`rt.astream`/`Flow`, which need no changes of
    their own as a result. Verified empirically against this project's pyright."""
    raise NotImplementedError


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
    tool_params: Iterable[Parameter] | None,
    middleware: Iterable[Middleware[_P, StringResponse]]
    | Iterable[Middleware[_P, StructuredResponse[_TBaseModel]]]
    | None = None,
    model_middleware: Iterable[ModelMiddleware] | None = None,
) -> type[Node[_P, StringResponse]] | type[Node[_P, StructuredResponse[_TBaseModel]]]:
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
            tool_params=list(tool_params) if tool_params is not None else None,
            middleware=cast(
                Iterable[Middleware[[UserInput], StringResponse]] | None, middleware
            ),
            model_middleware=model_middleware,
        )
    else:
        nb = LLMNodeBuilder.llm(
            name=name if name is not None else "LLM Agent",
            model=llm,
            system_message=resolved_system,
            schema=output_schema,
            tool_details=tool_details,
            tool_params=list(tool_params) if tool_params is not None else None,
            middleware=cast(
                Iterable[Middleware[[UserInput], StructuredResponse[_TBaseModel]]]
                | None,
                middleware,
            ),
            model_middleware=model_middleware,
        )

    return cast(
        type[Node[_P, StringResponse]]
        | type[Node[_P, StructuredResponse[_TBaseModel]]],
        nb.build(),
    )


# --- agent_node overloads (string vs structured output) ---


@overload
def agent_node(
    name: str | None = None,
    *,
    tool_nodes: Iterable[Type[Node] | RTFunction] | None = None,
    llm: ModelSource,
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
    middleware: Iterable[Middleware[_P, StringResponse]] | None = None,
    model_middleware: Iterable[ModelMiddleware] | None = None,
    _shape: Callable[_P, object] = _user_input_shape,
) -> type[Node[_P, StringResponse]]: ...


@overload
def agent_node(
    name: str | None = None,
    *,
    output_schema: Type[_TBaseModel],
    llm: ModelSource,
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
    middleware: Iterable[Middleware[_P, StructuredResponse[_TBaseModel]]] | None = None,
    model_middleware: Iterable[ModelMiddleware] | None = None,
    _shape: Callable[_P, object] = _user_input_shape,
) -> type[Node[_P, StructuredResponse[_TBaseModel]]]: ...


def agent_node(
    name: str | None = None,
    *,
    tool_nodes: Iterable[Type[Node] | RTFunction] | None = None,
    output_schema: Type[_TBaseModel] | None = None,
    llm: ModelSource,
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
    middleware: Iterable[Middleware[_P, StructuredResponse[_TBaseModel]]]
    | Iterable[Middleware[_P, StringResponse]]
    | None = None,
    model_middleware: Iterable[ModelMiddleware] | None = None,
    _shape: Callable[_P, object] = _user_input_shape,
) -> type[Node[_P, StringResponse]] | type[Node[_P, StructuredResponse[_TBaseModel]]]:
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
        _shape (Callable[_P, object]): Internal use only. Used to infer the ParamSpec for the agent's input shape.

    NOTE: Supplying a parameter `_shape` will break typing and you will be responsible for it. DO NOT USE THIS!!
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
    )
