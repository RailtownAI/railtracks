from typing import Literal, TypeVar

from ._llm_base import StringOutputMixIn
from ._tool_call_base import OutputLessToolCallLLM
from .response import StringResponse

_TStream = TypeVar("_TStream", Literal[True], Literal[False])


class ToolCallLLM(
    StringOutputMixIn,
    OutputLessToolCallLLM[StringResponse],
):
    pass
