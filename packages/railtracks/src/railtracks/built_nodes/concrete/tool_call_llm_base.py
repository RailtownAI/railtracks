from abc import ABC
from typing import Generator

from railtracks.llm.response import Response

from ._llm_base import StringOutputMixIn
from ._tool_call_base import OutputLessToolCallLLM
from .response import StringResponse


class ToolCallLLM(
    StringOutputMixIn,
    OutputLessToolCallLLM[StringResponse | Generator[str | Response, None, Response]],
    ABC,
):
    pass
