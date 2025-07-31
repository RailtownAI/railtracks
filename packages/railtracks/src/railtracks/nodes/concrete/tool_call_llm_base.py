from abc import ABC

from ._llm_base import StringOutputMixIn
from .response import StringResponse
from ._tool_call_base import OutputLessToolCallLLM


class ToolCallLLM(StringOutputMixIn, OutputLessToolCallLLM[StringResponse], ABC):
    pass
