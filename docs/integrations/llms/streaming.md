# Streaming

## What Is Streaming?

Streaming makes your agent feel responsive: instead of waiting for the complete response, token chunks are delivered as they arrive.

## The One Rule

**Streaming is requested at the call, not baked into the agent.** The same agent object serves streaming and non-streaming runs:

- `rt.call(agent, ...)` runs buffered — no streaming overhead, no chunks.
- `rt.astream(agent, ...)` streams — the agent's LLM responses are delivered chunk-by-chunk while it runs.

Streaming is also **frame-local**: only the node you invoke streams its LLM responses. Nested `rt.call` children (e.g. agents used as tools) run buffered — you will not see their tokens interleaved with the entry agent's.

## Pull — `rt.astream`

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

`Flow` supports the same pattern:

```python
--8<-- "docs/scripts/streaming.py:flow_astream"
```

## Push — `Stream.route()` and `stream_callback`

**Callbacks never enable streaming — only `astream` does.** For push-style consumption of a streamed call, `route()` the stream: it dispatches each chunk to your handler(s) by channel and returns the final result. Never construct a `Session` yourself — it is an internal object:

```python
--8<-- "docs/scripts/streaming.py:route"
```

Separately, a **`stream_callback`** (on the `Flow`, or globally via `rt.set_config`) is a *passive* session-wide listener for **stream chunks**: it receives every `rt.broadcast_stream` chunk of the run — LLM tokens included, from *any* scope (e.g. nested `astream`s) — but it does not turn streaming on. Prefer the dict form (channel name → callback); a bare callable is the firehose and receives every chunk on every channel.

One-off **events** published with `rt.broadcast` (progress notes, tool events, …) ride a separate lane: they go to the **`broadcast_callback`** — see [Broadcasting](../../observability/tracking/broadcasting.md). Streams are continuous productions; broadcasts are discrete events — the two callbacks keep those mental models apart:

```python
--8<-- "docs/scripts/streaming.py:stream_callback"
```

!!! Note "Which push consumer?"
    `route()` = **this call's** traffic (per-call isolated, enables the streaming, returns the result — it sees both chunks and events, separated by channel). `stream_callback` = **every streamed chunk in the session**, passively. `broadcast_callback` = **every `rt.broadcast` event in the session**, passively (buffered runs included — explicit broadcasts always flow). The end-of-run `payload_callback` is separate — it fires once with the serialized session payload.

!!! Tip "Unused-callback warnings"
    If a `stream_callback` / `broadcast_callback` (or any of its channel entries) never fires during a session, a `UserWarning` is emitted at close (visible by default, no logging setup needed) — distinguishing "nothing streamed (did you forget `astream`?)" from "traffic existed on other channels (channel-name typo?)". It even flags lane mix-ups: a `broadcast_callback` on a channel that only carried stream chunks is pointed to `stream_callback`, and vice versa. `route()` emits the same for handler channels that never matched.

## Custom Nodes — `rt.broadcast_stream`

Inside a custom node, call the model's streaming API directly and forward the stream to whoever is consuming the run with `rt.broadcast_stream`. It broadcasts each `str` chunk and returns the model's final complete `Response` (use `response.text` for its text content), so your node builds its return value as usual:

```python
--8<-- "docs/scripts/streaming.py:custom_node"
```

If nothing is listening (a plain `rt.call` with no consumers), the chunks are simply dropped and the node behaves exactly like a buffered call — the same node works in both modes.

For one-off **events** (progress messages, notes), `rt.broadcast(item, channel=...)` publishes a single item — but on the event lane: it reaches `broadcast_callback` (and scoped consumers like `route()`/`get_stream`), not `stream_callback`.

### Channels

Every chunk is emitted on a named channel (default: `"default"`). Channels let multiple streams coexist within one run and let consumers filter or route:

- Producers: `rt.broadcast_stream(gen, channel="draft")`, `rt.broadcast("note", channel="progress")`.
- Pull consumers: chain `.on_channel("final")` on the stream handle to yield only that channel (by default a stream yields everything in the run).
- Push consumers: `stream.route({"draft": fn1, "final": fn2})` for one call, or a passive `stream_callback` dict for the whole session.

```python
--8<-- "docs/scripts/streaming.py:custom_channels"
```

### Binding a prebuilt agent to a channel — `stream_channel`

Custom nodes pick their channel at each `broadcast_stream` call. Prebuilt agents bind theirs at construction with `agent_node(..., stream_channel="...")` — every token the agent streams (including every round of its tool-calling loop) is emitted on that bus. Combined with a passive `stream_callback` dict, different agents in one flow route to different consumers:

```python
--8<-- "docs/scripts/streaming.py:agent_stream_channel"
```

Note the nested `rt.astream(writer, ...)` inside the pipeline: nested `rt.call`s run buffered (frame-local rule), so a child agent must be *opted in* with a nested `astream` for its tokens to reach the bus. The binding is per node class, not per invocation — two agents needing different buses should be two `agent_node`s.

## Consuming a Channel From Inside a Run

`rt.astream` (with or without `route()`) and `stream_callback` both consume at the *top* of a run. To consume a channel **from inside** a run — e.g. an orchestrator node that runs a child concurrently and folds the child's live tokens into its own work — use `rt.context.get_stream(channel)`:

```python
--8<-- "docs/scripts/streaming.py:get_stream"
```

**Termination — counted end-markers.** Every `rt.broadcast_stream` is a bounded production: when it finishes (even if the producer raised), it publishes a `StreamEnd` marker on its channel, after all of its chunks. `get_stream` counts these markers:

- `streams=1` (default): stop after one production — the single-producer fold above ends by itself, no extra signal needed.
- `streams=N`: several producers share the channel; stop after N productions. (Channels are reused in practice — e.g. each round of a tool-calling agent is one production on the agent's channel.)
- `streams=None`: open-ended feed (unknown producers, or bare `rt.broadcast` items, which carry no markers) — bound the loop yourself with `break` or `until=task`.
- `until=task` (optional, combines with the above; whichever fires first wins): also useful as a **safety net** for a producer that crashes *before ever reaching* `broadcast_stream`, in which case no marker is published.

A channel itself never "closes" — a marker ends one production, not the channel. Other rules:

- Only chunks in the current stream scope are delivered (a child started with `rt.call` here is included; unrelated concurrent runs are not). Scope is keyed by `(stream_id, channel)`; in a plain non-streamed run `stream_id` is `None`, so give concurrent independent folds distinct channel names.
- The producer must broadcast explicitly (`rt.broadcast_stream` / `rt.broadcast`) — a nested `rt.call` is buffered otherwise (frame-local rule).
- Subscription is eager (at the `get_stream()` call), so chunks emitted before the loop starts are not missed.

!!! Tip "Simpler for a single call"
    To fold just one child call's stream, a nested `rt.astream(child, ...)` also works in one line — it launches the child, enables streaming on it, and isolates by its own scope. Reach for `get_stream` when several producers share a channel, or when you consume while doing other work in the same frame.

## Model-Level Streaming

At the lowest level, every model exposes `astream_chat` (and `astream_chat_with_tools` / `astream_structured`): async generators that yield `str` chunks followed by a single final `Response`:

```python
--8<-- "docs/scripts/streaming.py:model_astream"
```

This is what the framework uses internally, and what you pass to `rt.broadcast_stream` in custom nodes.

## Behavior Details

- **Tool-calling agents**: all text produced during the tool-call loop streams (including text in rounds that end in tool calls); tool-call arguments are not streamed. Tool nodes themselves run buffered (frame-local rule).
- **Structured output**: the raw JSON tokens stream; the final `StructuredResponse` is parsed and validated once the stream completes, so a schema failure surfaces at the end of the stream.
- **Guardrails**: output guardrails run on the complete buffered response. Streamed chunks are raw — already-emitted tokens cannot be recalled — but the final result is always the gated one.
- **Errors**: if the node fails mid-stream, the exception is raised out of the `async for` loop (or the `await`), exactly like `rt.call`.
- **Early exit**: `break`-ing out of the loop does not cancel the run — it continues to completion in the background. `await stream` afterwards to get the final result.
- **Timeouts**: the session's `timeout` applies to the whole streamed run as a wall-clock limit.

!!! Warning "Provider support for tool calling"
    Token streaming with **tool calling** is currently supported on OpenAI models only. Streamed runs of tool-calling agents on other providers automatically fall back to a buffered model call (a warning is logged) — the final result is unaffected; you just don't get incremental chunks.

!!! Warning "Deprecated: `stream=True` on the model"
    Constructing a model with `stream=True` (e.g. `OpenAILLM("gpt-4o", stream=True)`) is deprecated. It no longer changes agent behavior — agents built from such models return complete responses. Use `rt.astream(...)` (optionally with `.route(...)`) instead.
