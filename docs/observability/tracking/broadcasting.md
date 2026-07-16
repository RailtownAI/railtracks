# Broadcasting

Broadcasting lets you monitor your agents' progress in real time by sending live updates during execution. This can be useful for:

- Displaying progress in a UI or dashboard
- Logging intermediate steps for debugging
- Triggering alerts based on runtime events

Railtracks supports basic **data broadcasting**, enabling you to receive these updates via a callback function.

## Usage

To observe broadcasts, provide a **callback** to the `broadcast_callback` parameter on your `Flow` (or globally via `set_config`). Prefer the dict form mapping channel name -> callback to route items per channel; a bare callable receives every item on every channel. It is a *passive* listener — it never enables token streaming (see [Streaming](../../integrations/llms/streaming.md)); if it never fires during a session, a warning is logged at close.

```python
--8<-- "docs/scripts/broadcast.py:callback_creation"
```

With broadcasting enabled, call `rt.broadcast(...)` inside any function run in RT to invoke the handler.

```python
--8<-- "docs/scripts/broadcast.py:broadcast_call"
```

!!! warning
    Currently, only string messages can be broadcasted.


