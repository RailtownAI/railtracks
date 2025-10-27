from typing import Literal, TypeVar

from ._llm_base import StringOutputMixIn
from ._tool_call_base import OutputLessToolCallLLM, StreamingOutputLessToolCallLLM
from .response import StringResponse

_TStream = TypeVar("_TStream", Literal[True], Literal[False])


class ToolCallLLM(
    StringOutputMixIn,
    OutputLessToolCallLLM[StringResponse],
):
    pass


class StreamingToolCallLLM(
    StringOutputMixIn, StreamingOutputLessToolCallLLM[StringResponse]
):
    pass
