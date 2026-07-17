# Streaming

## What Is Streaming?

Streaming is a way to make your agent feel more responsive. Instead of waiting for the complete response, you can stream intermediate results as they arrive.


## Per-call Model Streaming

Streaming is requested per call via the model's `astream_*` methods (`astream_chat`,
`astream_chat_with_tools`, `astream_structured`). Each returns an async generator that yields
`str` token chunks as they arrive, followed by a single final `Response` containing the
complete message:

```python
--8<-- "docs/scripts/streaming.py:streaming_usage"
```

!!! Note
    Agent- and session-level streaming (forwarding a node's stream to whoever is consuming the
    run) is provided by the framework `astream` API, documented separately.

!!! Warning
    Streaming of tool calls is only supported for OpenAI models. Other providers fall back to a
    buffered response for tool-calling requests.
