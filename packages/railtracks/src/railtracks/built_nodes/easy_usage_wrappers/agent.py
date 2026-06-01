from types import FunctionType
from typing import Callable, Iterable, Literal, Type, TypeVar, overload

from pydantic import BaseModel

from railtracks.built_nodes.concrete import (
    RTFunction,
)
from railtracks.built_nodes.concrete._llm_base import LLMBase
from railtracks.built_nodes.concrete.rag import RagConfig, update_context
from railtracks.built_nodes.concrete.response import StringResponse, StructuredResponse
from railtracks.built_nodes.concrete.structured_llm_base import StreamingStructuredLLM
from railtracks.built_nodes.concrete.terminal_llm_base import StreamingTerminalLLM
from railtracks.built_nodes.concrete.tool_call_llm_base import StreamingToolCallLLM
from railtracks.built_nodes.llm_helpers import ModelGateway
from railtracks.guardrails.core import Guard
from railtracks.llm.message import SystemMessage
from railtracks.llm.model import ModelBase
from railtracks.llm.tools.parameter_handlers import ParameterHandler
from railtracks.llm.tools.parameters._base import Parameter
from railtracks.nodes.manifest import ToolManifest
from railtracks.nodes.nodes import Node
from railtracks.nodes.utils import extract_node_from_function



from .._node_builder import NodeBuilder, UserInput

_TBaseModel = TypeVar("_TBaseModel", bound=BaseModel)
_TStream = TypeVar("_TStream", Literal[True], Literal[False])


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
    llm: ModelBase[Literal[False]],
    system_message: SystemMessage | str | None,
    tool_details: str | None,
    tool_params: list[Parameter] | None,
):
    if output_schema is None:
        nb = NodeBuilder.llm(
            name=name if name is not None else "LLM Agent",
            model_gateway=ModelGateway(llm),
            system_message=SystemMessage(content=system_message) if isinstance(system_message, str) else system_message,
            connected_nodes=unpacked_tool_nodes,
            tool_details=tool_details,
            tool_params=tool_params,
        )
    else:
        nb = NodeBuilder.llm(
            name=name if name is not None else "LLM Agent",
            model_gateway=ModelGateway(llm),
            system_message=SystemMessage(content=system_message) if isinstance(system_message, str) else system_message,
            schema=output_schema,
            connected_nodes=unpacked_tool_nodes,
            tool_details=tool_details,
            tool_params=tool_params,
        )
    
    return nb.build()
    


# --- Tool-calling overloads (no guardrails) ---


@overload
def agent_node(
    name: str | None = None,
    *,
    tool_nodes: Iterable[Type[Node] | RTFunction] | None = None,
    output_schema: None = None,
    llm: ModelBase[Literal[False]],    
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
) -> type[Node[[UserInput], StringResponse]]: ...

@overload
def agent_node(
    name: str | None = None,
    *,
    tool_nodes: Iterable[Type[Node] | RTFunction] | None = None,
    output_schema: Type[_TBaseModel],
    llm: ModelBase[Literal[False]],    
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
) -> type[Node[[UserInput], StructuredResponse[_TBaseModel]]]: ...

def agent_node(
    name: str | None = None,
    *,
    tool_nodes: Iterable[Type[Node] | RTFunction] | None = None,
    output_schema: Type[_TBaseModel] | None = None,
    llm: ModelBase[Literal[False]],    
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
):
    """
    Dynamically creates an agent based on the provided parameters.

    Args:
        name (str | None): The name of the agent. If none the default will be used.
        rag (RagConfig | None): If your agent is a rag agent put in the vector store it is connected to.
        tool_nodes (set[Type[Node] | RTFunction] | None): If your agent is a LLM with access to tools, what does it have access to?
        output_schema (Type[_TBaseModel] | None): If your agent should return a structured output, what is the output_schema?
        llm (ModelBase): The LLM model to use. If None it will need to be passed in at instance time.
        system_message (SystemMessage | str | None): System message for the agent.
        manifest (ToolManifest | None): If you want to use this as a tool in other agents you can pass in a ToolManifest.
        guardrails (Guard | None): Guardrail config. When provided, the agent runs input/output guardrails.
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
    )


    return agent
