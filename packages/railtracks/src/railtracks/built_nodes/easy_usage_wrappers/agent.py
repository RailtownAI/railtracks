from types import FunctionType
from typing import Callable, Iterable, Literal, Type, TypeVar, overload

from pydantic import BaseModel

from railtracks.built_nodes.concrete import (
    RTFunction,
    StructuredLLM,
    StructuredToolCallLLM,
    TerminalLLM,
    ToolCallLLM,
)
from railtracks.built_nodes.concrete.structured_llm_base import StreamingStructuredLLM
from railtracks.built_nodes.concrete.terminal_llm_base import StreamingTerminalLLM
from railtracks.built_nodes.concrete.tool_call_llm_base import StreamingToolCallLLM
from railtracks.llm.message import SystemMessage
from railtracks.llm.model import ModelBase
from railtracks.nodes.manifest import ToolManifest
from railtracks.nodes.nodes import Node
from railtracks.nodes.utils import extract_node_from_function

from .helpers import (
    structured_llm,
    structured_tool_call_llm,
    terminal_llm,
    tool_call_llm,
)

_TBaseModel = TypeVar("_TBaseModel", bound=BaseModel)
_TStream = TypeVar("_TStream", Literal[True], Literal[False])


@overload
def agent_node(
    name: str | None = None,
    *,
    tool_nodes: Iterable[Type[Node] | Callable | RTFunction],
    output_schema: Type[_TBaseModel],
    llm: ModelBase[Literal[False]] | None = None,
    max_tool_calls: int | None = None,
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
) -> Type[StructuredToolCallLLM[_TBaseModel]]:
    pass


@overload
def agent_node(
    name: str | None = None,
    *,
    output_schema: Type[_TBaseModel],
    llm: ModelBase[Literal[True]],
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
) -> Type[StreamingStructuredLLM[_TBaseModel]]:
    pass


@overload
def agent_node(
    name: str | None = None,
    *,
    output_schema: Type[_TBaseModel],
    llm: ModelBase[Literal[False]] | None = None,
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
) -> Type[StructuredLLM[_TBaseModel]]:
    pass


@overload
def agent_node(
    name: str | None = None,
    *,
    llm: ModelBase[Literal[False]] | None = None,
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
) -> Type[TerminalLLM]:
    pass


@overload
def agent_node(
    name: str | None = None,
    *,
    llm: ModelBase[Literal[True]],
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
) -> Type[StreamingTerminalLLM]:
    pass


@overload
def agent_node(
    name: str | None = None,
    *,
    tool_nodes: Iterable[Type[Node] | Callable | RTFunction],
    llm: ModelBase[Literal[False]] | None = None,
    max_tool_calls: int | None = None,
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
) -> Type[ToolCallLLM]:
    pass


@overload
def agent_node(
    name: str | None = None,
    *,
    tool_nodes: Iterable[Type[Node] | Callable | RTFunction],
    llm: ModelBase[Literal[True]],
    max_tool_calls: int | None = None,
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
) -> Type[StreamingToolCallLLM]:
    pass


def agent_node(
    name: str | None = None,
    *,
    tool_nodes: Iterable[Type[Node] | Callable | RTFunction] | None = None,
    output_schema: Type[_TBaseModel] | None = None,
    llm: ModelBase[_TStream] | None = None,
    max_tool_calls: int | None = None,
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
):
    """
    Dynamically creates an agent based on the provided parameters.

    Args:
        name (str | None): The name of the agent. If none the default will be used.
        tool_nodes (set[Type[Node] | Callable | RTFunction] | None): If your agent is a LLM with access to tools, what does it have access to?
        output_schema (Type[_TBaseModel] | None): If your agent should return a structured output, what is the output_schema?
        llm (ModelBase): The LLM model to use. If None it will need to be passed in at instance time.
        max_tool_calls (int | None): Maximum number of tool calls allowed (if it is a ToolCall Agent).
        system_message (SystemMessage | str | None): System message for the agent.
        manifest (ToolManifest | None): If you want to use this as a tool in other agents you can pass in a ToolManifest.
    """
    unpacked_tool_nodes: set[Type[Node]] | None = None
    if tool_nodes is not None:
        unpacked_tool_nodes = set()
        for node in tool_nodes:
            if isinstance(node, FunctionType):
                unpacked_tool_nodes.add(extract_node_from_function(node))
            else:
                assert issubclass(node, Node), (
                    f"Expected {node} to be a subclass of Node"
                )
                unpacked_tool_nodes.add(node)

    # See issue (___) this logic should be migrated soon.
    if manifest is not None:
        tool_details = manifest.description
        tool_params = manifest.parameters
    else:
        tool_details = None
        tool_params = None

    if unpacked_tool_nodes is not None and len(unpacked_tool_nodes) > 0:
        if output_schema is not None:
            return structured_tool_call_llm(
                tool_nodes=unpacked_tool_nodes,
                output_schema=output_schema,
                name=name,
                llm=llm,
                max_tool_calls=max_tool_calls,
                system_message=system_message,
                tool_details=tool_details,
                tool_params=tool_params,
            )
        else:
            return tool_call_llm(
                tool_nodes=unpacked_tool_nodes,
                name=name,
                llm=llm,
                max_tool_calls=max_tool_calls,
                system_message=system_message,
                tool_details=tool_details,
                tool_params=tool_params,
            )
    else:
        if output_schema is not None:
            return structured_llm(
                output_schema=output_schema,
                name=name,
                llm=llm,
                system_message=system_message,
                tool_details=tool_details,
                tool_params=tool_params,
            )
        else:
            return terminal_llm(
                name=name,
                llm=llm,
                system_message=system_message,
                tool_details=tool_details,
                tool_params=tool_params,
            )
