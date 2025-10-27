from typing import Any, Callable, Iterable, Type, TypeVar

from pydantic import BaseModel

from railtracks.built_nodes._node_builder import NodeBuilder
from railtracks.built_nodes.concrete import StructuredLLM
from railtracks.built_nodes.concrete.structured_llm_base import StreamingStructuredLLM
from railtracks.llm import (
    ModelBase,
    SystemMessage,
)
from railtracks.llm.tools import Parameter

_TOutput = TypeVar("_TOutput", bound=BaseModel)


def structured_llm(
    output_schema: Type[_TOutput],
    *,
    system_message: SystemMessage | str | None = None,
    llm: ModelBase | None = None,
    name: str | None = None,
    tool_details: str | None = None,
    tool_params: Iterable[Parameter] | None = None,
    return_into: str | None = None,
    format_for_return: Callable[[Any], Any] | None = None,
    format_for_context: Callable[[Any], Any] | None = None,
) -> Type[StructuredLLM[_TOutput] | StreamingStructuredLLM[_TOutput]]:
    """
    Dynamically create a StructuredLastMessageLLM node class with custom configuration for output_schema.

    This easy-usage wrapper dynamically builds a node class that supports structured LLM output.
    This allows you to specify the output_schema, llm model, system message, tool metadata,
    and parameters. The returned class can be instantiated and used in the railtracks framework on runtime.

    Args:
        output_schema (Type[BaseModel]): The Pydantic model that defines the structure of the output.
        name (str, optional): Human-readable name for the node/tool.
        llm (ModelBase or None, optional): The LLM model instance to use for this node.
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
        StreamingStructuredLLM if llm is not None and llm.stream else StructuredLLM,
        name=name,
        class_name="EasyStructuredLastMessageLLM",
        return_into=return_into,
        format_for_return=format_for_return,
        format_for_context=format_for_context,
    )
    builder.llm_base(llm, system_message)
    builder.structured(output_schema)
    if tool_details is not None or tool_params is not None:
        builder.tool_callable_llm(tool_details, tool_params)

    return builder.build()
