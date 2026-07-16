# Broadcasting

Broadcasting lets you monitor your agents' progress in real time by sending live updates during execution. This can be useful for:

- Displaying progress in a UI or dashboard
- Logging intermediate steps for debugging
- Triggering alerts based on runtime events

Railtracks supports basic **data broadcasting**, enabling you to receive these updates via a callback function.

## Usage

To enable broadcasting, provide a **callback function** to the `stream_callback` parameter in `set_config` (or on your `Flow`). It receives every broadcast item; pass a dict mapping channel name -> callback to route items per channel. Note: providing a `stream_callback` also enables token streaming for top-level calls (see [Streaming](../../integrations/llms/streaming.md)).

```python
--8<-- "docs/scripts/broadcast.py:callback_creation"
```

With broadcasting enabled, call `rt.broadcast(...)` inside any function run in RT to invoke the handler.

```python
--8<-- "docs/scripts/broadcast.py:broadcast_call"
```

!!! warning
    Currently, only string messages can be broadcasted.


