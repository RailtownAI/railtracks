# Streaming

## What is streaming?

Streaming makes an agent feel more responsive. Instead of waiting for the whole response, you receive the tokens as they are produced.

## Streaming an agent run with `rt.astream`

Streaming is requested at the call site rather than baked into the agent, so the same agent object works either way:

- `rt.call(agent, ...)` runs buffered, with no streaming overhead and no chunks.
- `rt.astream(agent, ...)` streams the agent's LLM response chunk by chunk as it runs.

`rt.astream` targets **agent nodes only**. Passing a `@function_node` (or any non-agent node) raises an error; run those with `rt.call` and reach for `rt.astream` on the agent inside them.

`rt.astream` returns a `Stream`, an async iterator that yields only the `str` chunks. The final result is kept separate and read from `.result` once the stream is exhausted, so a chunk is never confused with the final value:

```python
--8<-- "docs/scripts/streaming.py:astream_basic"
```

A `Stream` is also awaitable. Awaiting it consumes the stream to completion and returns the final result:

```python
--8<-- "docs/scripts/streaming.py:astream_await"
```

!!! Note "The final result is authoritative"
    `stream.result` can differ from the concatenation of the streamed chunks. For example, an output guardrail may correct the buffered response after the raw tokens were already streamed. Treat the chunks as live progress and `.result` as the answer.

A few details worth knowing:

- **Frame-local.** Only the agent you invoke streams its LLM response. Nested `rt.call` children, such as agents used as tools, run buffered.
- **Errors.** If the node fails mid-stream, the exception is raised out of the `async for` loop (or the `await`), just as it is with `rt.call`.
- **Early exit.** Breaking out of the loop does not cancel the run; it finishes in the background. Await the stream afterwards to collect the final result.
- **Timeouts.** The session `timeout` applies to the whole streamed run as a wall-clock limit.
- **Tool calling.** Token streaming with tool calling is currently supported on OpenAI models only. On other providers a streamed tool-calling run falls back to a buffered model call (with a logged warning), and the final result is unaffected.

### Streaming inside a `@function_node`

Because `rt.astream` targets an agent, the natural pattern is to stream the agent from inside a `@function_node` and drive that outer node with `rt.call`. The chunks are delivered straight to your handl.

```python
--8<-- "docs/scripts/streaming.py:astream_nested"
```
