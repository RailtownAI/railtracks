from ._llm_base import StringOutputMixIn
from ._tool_call_base import OutputLessToolCallLLM
from .response import StringResponse


class ToolCallLLM(
    StringOutputMixIn,
    OutputLessToolCallLLM[StringResponse],
):
    """A tool-calling LLM node that returns the final assistant text as a `StringResponse`.

    Streaming: when invoked through `rt.astream` (or with a `stream_callback` configured), all
    text produced during the tool-call loop is streamed chunk-by-chunk; the node still returns
    the complete `StringResponse` at the end. Nested tool nodes always run buffered.
    """

    pass
