from types import FunctionType
from typing import Callable, Iterable, Literal, Type, TypeVar, overload

from pydantic import BaseModel

from railtracks.built_nodes.concrete import (
    GuardedStreamingStructuredLLM,
    GuardedStreamingTerminalLLM,
    GuardedStructuredLLM,
    GuardedTerminalLLM,
    RTFunction,
    StructuredLLM,
    StructuredToolCallLLM,
    TerminalLLM,
    ToolCallLLM,
)
from railtracks.built_nodes.concrete._llm_base import LLMBase
from railtracks.built_nodes.concrete.rag import RagConfig, update_context
from railtracks.built_nodes.concrete.structured_llm_base import StreamingStructuredLLM
from railtracks.built_nodes.concrete.terminal_llm_base import StreamingTerminalLLM
from railtracks.built_nodes.concrete.tool_call_llm_base import StreamingToolCallLLM
from railtracks.guardrails.core import Guard
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


def _unpack_tool_nodes(
    tool_nodes: Iterable[Type[Node] | Callable | RTFunction] | None,
) -> set[Type[Node]] | None:
    if tool_nodes is None:
        return None
    unpacked: set[Type[Node]] = set()
    for node in tool_nodes:
        if isinstance(node, FunctionType):
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
    llm: ModelBase[_TStream] | None,
    system_message: SystemMessage | str | None,
    tool_details: str | None,
    tool_params: set | Iterable | None,
    guardrails: Guard | None,
):
    if unpacked_tool_nodes is not None and len(unpacked_tool_nodes) > 0:
        if guardrails is not None:
            raise NotImplementedError(
                "Guardrails are not yet supported for tool-calling agents (see https://github.com/RailtownAI/railtracks/issues/1047)."
            )
        if output_schema is not None:
            return structured_tool_call_llm(
                tool_nodes=unpacked_tool_nodes,
                output_schema=output_schema,
                name=name,
                llm=llm,
                system_message=system_message,
                tool_details=tool_details,
                tool_params=tool_params,
            )
        return tool_call_llm(
            tool_nodes=unpacked_tool_nodes,
            name=name,
            llm=llm,
            system_message=system_message,
            tool_details=tool_details,
            tool_params=tool_params,
        )
    if output_schema is not None:
        return structured_llm(
            output_schema=output_schema,
            name=name,
            llm=llm,
            guardrails=guardrails,
            system_message=system_message,
            tool_details=tool_details,
            tool_params=tool_params,
        )
    return terminal_llm(
        name=name,
        llm=llm,
        guardrails=guardrails,
        system_message=system_message,
        tool_details=tool_details,
        tool_params=tool_params,
    )


# --- Tool-calling overloads (guardrails not supported yet) ---


@overload
def agent_node(
    name: str | None = None,
    *,
    rag: RagConfig | None = None,
    tool_nodes: Iterable[Type[Node] | Callable | RTFunction],
    output_schema: Type[_TBaseModel],
    llm: ModelBase[Literal[False]] | None = None,
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
) -> Type[StructuredToolCallLLM[_TBaseModel]]:
    pass


@overload
def agent_node(
    name: str | None = None,
    *,
    rag: RagConfig | None = None,
    tool_nodes: Iterable[Type[Node] | Callable | RTFunction],
    llm: ModelBase[Literal[False]] | None = None,
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
) -> Type[ToolCallLLM]:
    pass


@overload
def agent_node(
    name: str | None = None,
    *,
    rag: RagConfig | None = None,
    tool_nodes: Iterable[Type[Node] | Callable | RTFunction],
    llm: ModelBase[Literal[True]],
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
) -> Type[StreamingToolCallLLM]:
    pass


# --- Structured overloads (no guardrails) ---


@overload
def agent_node(
    name: str | None = None,
    *,
    rag: RagConfig | None = None,
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
    rag: RagConfig | None = None,
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
    rag: RagConfig | None = None,
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
    rag: RagConfig | None = None,
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
    rag: RagConfig | None = None,
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
    rag: RagConfig | None = None,
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
    rag: RagConfig | None = None,
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
    rag: RagConfig | None = None,
    llm: ModelBase[Literal[True]],
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
    guardrails: Guard,
) -> Type[GuardedStreamingTerminalLLM]:
    pass


def agent_node(
    name: str | None = None,
    *,
    rag: RagConfig | None = None,
    tool_nodes: Iterable[Type[Node] | Callable | RTFunction] | None = None,
    output_schema: Type[_TBaseModel] | None = None,
    llm: ModelBase[_TStream] | None = None,
    system_message: SystemMessage | str | None = None,
    manifest: ToolManifest | None = None,
    guardrails: Guard | None = None,
):
    """
    Dynamically creates an agent based on the provided parameters.

    Args:
        name (str | None): The name of the agent. If none the default will be used.
        rag (RagConfig | None): If your agent is a rag agent put in the vector store it is connected to.
        tool_nodes (set[Type[Node] | Callable | RTFunction] | None): If your agent is a LLM with access to tools, what does it have access to?
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
        guardrails=guardrails,
    )

    if rag is not None:

        def _update_message_history(node: Node):
            # `pre_invokes` may be shared across Node subclasses; only LLM agents
            # have `message_hist` / RAG context to update.
            if not isinstance(node, LLMBase):
                return
            node.message_hist = update_context(
                node.message_hist, vs=rag.vector_store, top_k=rag.top_k
            )

        agent.add_pre_invoke(_update_message_history)

    return agent
