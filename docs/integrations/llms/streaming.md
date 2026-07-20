# Streaming

## What Is Streaming?

Streaming is a way to make your agent feel more responsive. Instead of waiting for the complete response, you can stream intermediate results as they arrive.

## Streaming an Agent Run — `rt.astream`

Streaming is requested at the **call**, not baked into the agent. The same agent object serves streaming and non-streaming runs:

- `rt.call(agent, ...)` runs buffered — no streaming overhead, no chunks.
- `rt.astream(agent, ...)` streams — the agent's LLM responses are delivered chunk-by-chunk while it runs.

`rt.astream` returns a `Stream` handle: an async iterator that yields **only** `str` chunks. The final result is available separately via `.result` once the stream is exhausted, so there is never any ambiguity between a chunk and the final value:

```python
--8<-- "docs/scripts/streaming.py:astream_basic"
```

A `Stream` is also awaitable — `await stream` consumes it to completion and returns the final result:

```python
--8<-- "docs/scripts/streaming.py:astream_await"
```

!!! Note "The final result is authoritative"
    `stream.result` may differ from the concatenation of the streamed chunks — for example when output guardrails gate or correct the buffered response after the raw tokens were streamed. Treat the chunks as live progress and `.result` as the answer.

Behavior details:

- **Frame-local**: only the node you invoke streams its LLM responses. Nested `rt.call` children (e.g. agents used as tools) run buffered.
- **Errors**: if the node fails mid-stream, the exception is raised out of the `async for` loop (or the `await`), exactly like `rt.call`.
- **Early exit**: `break`-ing out of the loop does not cancel the run — it continues to completion in the background. `await stream` afterwards to get the final result.
- **Timeouts**: the session's `timeout` applies to the whole streamed run as a wall-clock limit.
- **Tool calling**: token streaming with tool calling is currently supported on OpenAI models only. Streamed runs of tool-calling agents on other providers automatically fall back to a buffered model call (a warning is logged) — the final result is unaffected.

### Two callback lanes: `broadcast_callback` vs `stream_callback`

Streaming rides the same pubsub bus as `rt.broadcast`, but the two kinds of traffic are kept on **separate lanes** so a listener is never handed the wrong thing:

- **`stream_callback`** — a passive session-wide listener for **stream chunks** (`rt.broadcast_stream` productions, which include all LLM token streaming). This is the callback form of consuming tokens; `rt.astream` is the pull form.
- **`broadcast_callback`** — a passive session-wide listener for one-off **events** published with `rt.broadcast` (progress notes, tool events). It is *never* flooded with tokens, even while a run streams.

Both are set on the `Flow` (or globally via `rt.set_config`), and neither one *enables* streaming — only `rt.astream` does.

```python
--8<-- "docs/scripts/streaming.py:stream_callback"
```

## Streaming Support
Railtracks supports streaming responses from your agent. To interact with a stream, just set the appropriate flag when creating your LLM.

```python
--8<-- "docs/scripts/streaming.py:streaming_flag"
```

When you call the LLM, it will return a generator that you can iterate through:

```python
--8<-- "docs/scripts/streaming.py:streaming_usage"
```

## Agent Support

Agents in Railtracks also support streamed responses. When creating your agent, you provide an LLM with streaming enabled:

```python
--8<-- "docs/scripts/streaming.py:streaming_with_agents"
```

The output of the agent will be a generator containing a sequence of strings, followed by the complete message.

!!! Example "Usage"
    ```python    
    --8<-- "docs/scripts/streaming.py:streaming_agent_usage"
    ```
    `

!!! Warning
    When using streaming, you should fully exhaust the returned object within the session. If you do this outside of the session, the visualizer suite will not work as expected.

!!! Warning 
    Streaming is only supported for tool-calling agents if you are using openai.



