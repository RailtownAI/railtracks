# Streaming

## What is streaming?

Streaming makes an agent feel more responsive. Instead of waiting for the whole response, you receive the tokens as they are produced.

## Streaming an agent run with `rt.astream`

Streaming is requested at the call site rather than baked into the agent, so the same agent object works either way:

- `rt.call(agent, ...)` runs buffered, with no streaming overhead and no chunks.
- `rt.astream(agent, ...)` streams the agent's LLM response chunk by chunk as it runs.

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

- **Frame-local.** Only the node you invoke streams its LLM response. Nested `rt.call` children, such as agents used as tools, run buffered.
- **Errors.** If the node fails mid-stream, the exception is raised out of the `async for` loop (or the `await`), just as it is with `rt.call`.
- **Early exit.** Breaking out of the loop does not cancel the run; it finishes in the background. Await the stream afterwards to collect the final result.
- **Timeouts.** The session `timeout` applies to the whole streamed run as a wall-clock limit.
- **Tool calling.** Token streaming with tool calling is currently supported on OpenAI models only. On other providers a streamed tool-calling run falls back to a buffered model call (with a logged warning), and the final result is unaffected.

### Named channels

Every streamed item travels on a named channel. An agent's tokens ride the `"default"` channel, and you can send your own one-off events on any channel with `rt.broadcast(item, channel=...)` from inside a run:

```python
--8<-- "docs/scripts/streaming.py:channels"
```

By default a `Stream` yields chunks from every channel. When a run produces on more than one channel (say, the agent's tokens on `"default"` and progress notes on `"status"`), chain `on_channel` to consume just one:

```python
async for token in rt.astream(agent, user_input="...").on_channel("default"):
    ...
```

`on_channel` is a method rather than an `astream(..., channel=...)` keyword because `astream` forwards its keyword arguments to the node, where a `channel` keyword could collide with the node's own parameters.

### Two callback lanes: `broadcast_callback` and `stream_callback`

Streaming shares the same pubsub bus as `rt.broadcast`, but the two kinds of traffic travel on separate lanes so a listener never receives the wrong kind:

- **`stream_callback`** is a passive, session-wide listener for stream chunks, meaning the `rt.broadcast_stream` productions that carry LLM tokens. It is the callback form of consuming tokens, where `rt.astream` is the pull form.
- **`broadcast_callback`** is a passive, session-wide listener for one-off events sent with `rt.broadcast`, such as progress notes or tool events. It never receives token chunks, even while a run streams.

Both are set on the `Flow` or globally with `rt.set_config`, and neither one turns streaming on. Only `rt.astream` does that.

```python
--8<-- "docs/scripts/streaming.py:stream_callback"
```
