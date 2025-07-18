from typing import Any, Callable, Type

from pydantic import BaseModel

from requestcompletion.llm import (
    ModelBase,
    SystemMessage,
)
from requestcompletion.nodes._node_builder import NodeBuilder
from requestcompletion.nodes.library.structured_llm import StructuredLLM

from ....llm.tools import Parameter


def structured_llm(  # noqa: C901
    schema: Type[BaseModel],
    *,
    system_message: SystemMessage | str | None = None,
    llm_model: ModelBase | None = None,
    pretty_name: str | None = None,
    tool_details: str | None = None,
    tool_params: set[Parameter] | None = None,
    return_into: str | None = None,
    format_for_return: Callable[[Any], Any] | None = None,
    format_for_context: Callable[[Any], Any] | None = None,
) -> Type[StructuredLLM]:
    """
    Dynamically reate a StructuredLLM node class with custom configuration for schema.

    This easy-usage wrapper dynamically builds a node class that supports structured LLM output.
    This allows you to specify the schema, llm model, system message, tool metadata,
    and parameters. The returned class can be instantiated and used in the requestcompletion framework on runtime.

    Args:
        schema (Type[BaseModel]): The Pydantic model that defines the structure of the output.
        pretty_name (str, optional): Human-readable name for the node/tool.
        llm_model (ModelBase or None, optional): The LLM model instance to use for this node.
        system_message (SystemMessage or str or None, optional): The system prompt/message for the node. If not passed here it can be passed at runtime in message history.
        tool_details (str or None, optional): Description of the node subclass for other LLMs to know how to use this as a tool.
        tool_params (set of params or None, optional): Parameters that must be passed if other LLMs want to use this as a tool.
        return_into (str, optional): The key to store the result of the tool call into context. If not specified, the result will not be put into context.
        format_for_return (Callable[[Any], Any] | None, optional): A function to format the result before returning it, only if return_into is provided. If not specified when while return_into is provided, None will be returned.
        format_for_context (Callable[[Any], Any] | None, optional): A function to format the result before putting it into context, only if return_into is provided. If not provided, the response will be put into context as is.

    Returns:
        Type[StructuredLLM]: The dynamically generated node class with the specified configuration.
    """
    builder = NodeBuilder(
        StructuredLLM,
        pretty_name=pretty_name,
        class_name="EasyStructuredLLM",
        return_into=return_into,
        format_for_return=format_for_return,
        format_for_context=format_for_context,
    )
    builder.llm_base(llm_model, system_message)
    builder.structured(schema)
    if tool_details is not None or tool_params is not None:
        builder.tool_callable_llm(tool_details, tool_params)

    return builder.build()
