# ToolOutputSummarizer

`ToolOutputSummarizer` replaces oversized text tool results in an agent's model history with a concise summary. It is model middleware: use `model_middleware=` on an agent. Results at or below `max_chars` are left untouched.

The summary model is called without the agent's tools. Its input is bounded by `input_max_chars`; when a result is longer, the beginning and end are retained around an omission marker. A summary is bounded by `summary_max_chars`. If the summarizer errors or returns no text, the original result is retained and the agent continues.

```python
import railtracks as rt
from railtracks.prebuilt.middleware import ToolOutputSummarizer

agent = rt.agent_node(
    "Researcher",
    llm=rt.llm.OpenAILLM(model_name="gpt-4o-mini"),
    tool_nodes=[search_node],
    model_middleware=[
        ToolOutputSummarizer(
            summarizer=rt.llm.OpenAILLM(model_name="gpt-4o-mini"),
            max_chars=4_000,
            summary_max_chars=1_000,
            input_max_chars=20_000,
        )
    ],
)
```

The summary model makes a separate model request for each oversized text result. Choose a fast, inexpensive model and thresholds that suit the cost and latency budget of your application. The source text is treated as untrusted data in the summarization prompt; as with any model-generated summary, verify important details before acting on them.
