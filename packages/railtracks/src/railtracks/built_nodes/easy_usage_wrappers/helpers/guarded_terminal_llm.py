from typing import Any, Callable

from railtracks.built_nodes._node_builder import NodeBuilder
from railtracks.built_nodes.concrete import GuardedTerminalLLM
from railtracks.exceptions import NodeCreationError
from railtracks.guardrails.core import Guard
from railtracks.llm import ModelBase, SystemMessage
from railtracks.llm.tools import Parameter


def guarded_terminal_llm(
    name: str | None = None,
    *,
    system_message: SystemMessage | str | None = None,
    llm: ModelBase | None = None,
    guardrails: Guard,
    tool_details: str | None = None,
    tool_params: set[Parameter] | None = None,
    return_into: str | None = None,
    format_for_return: Callable[[Any], Any] | None = None,
    format_for_context: Callable[[Any], Any] | None = None,
):
    """
    Dynamically create a guarded terminal LLM node class with custom configuration.

    Guardrails are enforced at node-level (not model-hook-level).
    Streaming guarded terminal LLM is intentionally deferred.
    """

    if llm is not None and getattr(llm, "stream", False):
        raise NodeCreationError(
            message="Guarded streaming terminal LLM is not implemented yet.",
            notes=[
                "For now, use non-streaming models with guardrails.",
                "Add GuardedStreamingTerminalLLM as a follow-up (see phase-1.5 TODO).",
            ],
        )

    builder = NodeBuilder(
        GuardedTerminalLLM,
        name=name,
        class_name="EasyGuardedTerminalLLM",
        return_into=return_into,
        format_for_return=format_for_return,
        format_for_context=format_for_context,
    )
    builder.llm_base(llm, system_message)
    builder.add_attribute("guardrails", guardrails, make_function=False)
    if tool_details is not None or tool_params is not None:
        builder.tool_callable_llm(tool_details, tool_params)

    return builder.build()
