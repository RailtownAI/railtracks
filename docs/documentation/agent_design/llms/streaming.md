# Streaming

## What Is Streaming?

Streaming makes your agent feel more responsive. Instead of waiting for the
complete response, tokens are delivered as they arrive.

## Agent Streaming (Recommended)

Pass `stream=True` to both the LLM and `agent_node`. The node still returns
`StringResponse` / `StructuredResponse` — streaming is a delivery detail, not
a change to the pipeline interface.

```python
--8<-- "docs/scripts/streaming.py:v2_streaming_agent"
```

### `astream()` — pull-based (iterate chunks directly)

Use `Flow.astream()` when you want to consume chunks inline with `async for`.
The generator yields `str` chunks in real time and the terminal
`StringResponse` as the final item:

```python
--8<-- "docs/scripts/streaming.py:astream_usage"
```

### `ainvoke()` — push-based (callback)

Use `Flow.ainvoke()` with a `broadcast_callback` when you need to push chunks
to an external sink (WebSocket, SSE, async queue) while your code continues
doing other work:

```python
--8<-- "docs/scripts/streaming.py:v2_streaming_callback"
```

The callback may be a plain `def` or an `async def`.

!!! Note
    `model_middleware` entry gates run once before the first chunk; exit gates
    run once on the terminal `Response`. Existing `@rt.wrapper` wrappers work
    unchanged in the streaming path. To intercept individual chunks, write an
    async generator wrapper — `@wrapper` auto-detects the shape:

    ```python
    @rt.wrapper
    async def log_chunks(call, *args, **kwargs):
        async for chunk in call(*args, **kwargs):
            print(chunk, end="")
            yield chunk
    ```

## Direct LLM Streaming (Legacy)

For scripts that call the LLM directly without an agent, `stream=True` on the
LLM returns a generator you iterate yourself:

```python
--8<-- "docs/scripts/streaming.py:streaming_flag"
```

```python
--8<-- "docs/scripts/streaming.py:streaming_usage"
```

If you use this pattern inside an agent flow:

```python
--8<-- "docs/scripts/streaming.py:streaming_agent_usage"
```

!!! Warning
    When using direct LLM streaming you should fully exhaust the returned
    generator within the session. Iterating outside the session means the
    visualiser suite will not work as expected.

!!! Warning
    Direct LLM streaming with tool-calling agents is only supported for OpenAI.
