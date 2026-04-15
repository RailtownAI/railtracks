from typing import Any, Callable

from railtracks.built_nodes._node_builder import NodeBuilder
from railtracks.built_nodes.concrete.guarded_llm import (
    GuardedStreamingTerminalLLM,
    GuardedTerminalLLM,
)
from railtracks.built_nodes.concrete.terminal_llm_base import (
    StreamingTerminalLLM,
    TerminalLLM,
)
from railtracks.guardrails.core import Guard
from railtracks.llm import ModelBase, SystemMessage
from railtracks.llm.tools import Parameter


def terminal_llm(
    name: str | None = None,
    *,
    system_message: SystemMessage | str | None = None,
    llm: ModelBase | None = None,
    guardrails: Guard | None = None,
    tool_details: str | None = None,
    tool_params: set[Parameter] | None = None,
    return_into: str | None = None,
    format_for_return: Callable[[Any], Any] | None = None,
    format_for_context: Callable[[Any], Any] | None = None,
):
    """
    Dynamically create a LastMessageTerminalLLM node class with custom configuration.

    This easy-usage wrapper dynamically builds a node class that supports a basic LLM.
    This allows you to specify the llm model, system message, tool metadata, and parameters.
    The returned class can be instantiated and used in the railtracks framework on runtime.

    Args:
        name (str, optional): Human-readable name for the node/tool.
        llm (ModelBase or None, optional): The LLM model instance to use for this node.
        system_message (SystemMessage or str or None, optional): The system prompt/message for the node. If not passed here it can be passed at runtime in message history.
        guardrails (Guard or None, optional): Guardrail config. When provided, the node runs input/output guardrails.
        tool_details (str or None, optional): Description of the node subclass for other LLMs to know how to use this as a tool.
        tool_params (set of params or None, optional): Parameters that must be passed if other LLMs want to use this as a tool.
        return_into (str, optional): The key to store the result of the tool call into context. If not specified, the result will not be put into context.
        format_for_return (Callable[[Any], Any] | None, optional): A function to format the result before returning it, only if return_into is provided. If not specified when while return_into is provided, None will be returned.
        format_for_context (Callable[[Any], Any] | None, optional): A function to format the result before putting it into context, only if return_into is provided. If not provided, the response will be put into context as is.

    Returns:
        Type[LastMessageTerminalLLM]: The dynamically generated node class with the specified configuration.
    """
    is_streaming = llm is not None and llm.stream

    if guardrails is not None:
        base_cls = GuardedStreamingTerminalLLM if is_streaming else GuardedTerminalLLM
    else:
        base_cls = StreamingTerminalLLM if is_streaming else TerminalLLM

    builder = NodeBuilder(
        base_cls,
        name=name,
        class_name="EasyLastMessageTerminalLLM",
        return_into=return_into,
        format_for_return=format_for_return,
        format_for_context=format_for_context,
    )
    builder.llm_base(llm, system_message)
    if guardrails is not None:
        builder.add_attribute("guardrails", guardrails, make_function=False)
    if tool_details is not None or tool_params is not None:
        builder.tool_callable_llm(tool_details, tool_params)

    return builder.build()
