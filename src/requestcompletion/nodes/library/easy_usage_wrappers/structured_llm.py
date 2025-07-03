from typing import Type, Dict, Any
from copy import deepcopy
from requestcompletion.llm import (
    ModelBase,
    SystemMessage,
)
from typing_extensions import Self
from requestcompletion.exceptions.node_creation.validation import validate_tool_metadata
from requestcompletion.exceptions.node_invocation.validation import check_model, check_message_history
from requestcompletion.nodes.library.easy_usage_wrappers._structured_llm import StructuredBase
from pydantic import BaseModel


def structured_llm(  # noqa: C901
    output_model: Type[BaseModel],
    system_message: SystemMessage | str | None = None,
    model: ModelBase | None = None,
    pretty_name: str | None = None,
    tool_details: str | None = None,
    tool_params: dict | None = None,
) -> Type[StructuredBase]:
    class StructuredLLM(StructuredBase,
                        output_model=output_model,
                        system_message=system_message,
                        model=model,
                        pretty_name=pretty_name,
                        tool_details=tool_details,
                        tool_params=tool_params,
                        ):

        @classmethod
        def output_model(cls) -> Type[BaseModel]:
            return cls._output_model

    return StructuredLLM
