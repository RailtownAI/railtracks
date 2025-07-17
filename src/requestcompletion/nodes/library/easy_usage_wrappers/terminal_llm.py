from typing import Type

from requestcompletion.nodes.library.easy_usage_wrappers.node_builder import NodeBuilder

from ....llm import ModelBase, SystemMessage
from ....llm.tools import Parameter
from ..terminal_llm import TerminalLLM


def terminal_llm(  # noqa: C901
    pretty_name: str | None = None,
    *,
    system_message: SystemMessage | str | None = None,
    llm_model: ModelBase | None = None,
    tool_details: str | None = None,
    tool_params: set[Parameter] | None = None,
) -> Type[TerminalLLM]:
    """
    Dynamically create a TerminalLLM node class with custom configuration.

    This easy-usage wrapper dynamically builds a node class that supports a basic LLM.
    This allows you to specify the llm model, system message, tool metadata, and parameters.
    The returned class can be instantiated and used in the requestcompletion framework on runtime.

    Parameters
    ----------
    pretty_name : str, optional
        Human-readable name for the node/tool.
    llm_model : ModelBase or None, optional
        The LLM model instance to use for this node.
    system_message : SystemMessage or str or None, optional
        The system prompt/message for the node. If not passed here it can be passed at runtime in message history.
    tool_details : str or None, optional
        Description of the node subclass for other LLMs to know how to use this as a tool.
    tool_params : set of params or None, optional
        Parameters that must be passed if other LLMs want to use this as a tool.

    Returns
    -------
    Type[TerminalLLM]
        The dynamically generated node class with the specified configuration.

    """
    builder = NodeBuilder(
        TerminalLLM,
        pretty_name=pretty_name,
        class_name="EasyTerminalLLM",
        tool_details=tool_details,
        tool_params=tool_params,
    )
    builder.llm_base(llm_model, system_message)
    if tool_details is not None:
        builder.tool_callable_llm(tool_details, tool_params)

    return builder.build()
