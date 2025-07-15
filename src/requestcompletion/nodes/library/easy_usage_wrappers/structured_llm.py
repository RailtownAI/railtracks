from typing import Type
from requestcompletion.llm import (
    ModelBase,
    SystemMessage,
)
from requestcompletion.nodes.library.easy_usage_wrappers.node_builder import NodeBuilder
from requestcompletion.nodes.library.structured_llm import StructuredLLM
from pydantic import BaseModel


def structured_llm(  # noqa: C901
    output_model: Type[BaseModel],
    system_message: SystemMessage | str | None = None,
    llm_model: ModelBase | None = None,
    pretty_name: str | None = None,
    tool_details: str | None = None,
    tool_params: dict | None = None,
) -> Type[StructuredLLM]:
    builder = NodeBuilder(
        StructuredLLM,
        pretty_name=pretty_name,
        class_name="EasyStructuredLLM",
        tool_details=tool_details,
        tool_params=tool_params,
    )
    builder.llm_base(llm_model, system_message)
    builder.structured(output_model)
    if tool_details is not None:
        builder.tool_callable_llm(tool_details, tool_params)

    return builder.build()
