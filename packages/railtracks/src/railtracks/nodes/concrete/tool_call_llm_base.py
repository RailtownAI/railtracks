from abc import ABC

from ._llm_base import StringOutputMixIn
from ._tool_call_base import OutputLessToolCallLLM
from .response import StringResponse


class ToolCallLLM(StringOutputMixIn, OutputLessToolCallLLM[StringResponse], ABC):
    pass
