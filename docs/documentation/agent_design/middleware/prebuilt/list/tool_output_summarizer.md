# ToolOutputSummarizer

`ToolOutputSummarizer` replaces oversized text tool results in an agent's model history with a concise summary. It is model middleware: use `model_middleware=` on an agent. Results at or below `max_chars` and non-text results are left untouched. Originals remain in the returned `message_history`; only the model sees summaries.

The summary model, or no-argument model factory, runs as a `ToolOutputSummarizer` node without the agent's tools. Its calls, tokens, and cost are recorded through the normal node/model observability pipeline. Its input includes at most `input_max_chars` source characters; when a result is longer, the beginning and end are retained around an omission marker. The summary body is bounded by `summary_max_chars`, with a separate `[Summarized: original was … characters]` header so the agent knows it is reading a partial view. The character budget is also included in the prompt.

```python
--8<-- "docs/scripts/prebuilt_middleware.py:tool_output_summarizer"
```

Each oversized result is summarized once per agent invocation, keyed by its tool-call identifier. Later turns reuse the summary; separate or concurrent invocations have separate caches, even when their tool-call identifiers match. Independent results from parallel tool calls are summarized concurrently. If summarization errors or returns no text, the original result is retained for the rest of that invocation rather than repeatedly retrying a failed summary.

Place `ToolOutputSummarizer` before any model middleware that should see shorter text, such as an input guard. Middleware listed earlier sees the original tool results.

Choose a fast, inexpensive summary model and thresholds that suit the cost and latency budget of your application. The source text is treated as untrusted data in the summarization prompt; as with any model-generated summary, verify important details before acting on them.
