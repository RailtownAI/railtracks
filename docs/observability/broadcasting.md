# Broadcasting

Broadcasting lets you monitor your agents' progress in real time by sending live updates during execution. This can be useful for:

- Displaying progress in a UI or dashboard
- Logging intermediate steps for debugging
- Triggering alerts based on runtime events

Railtracks supports basic **data broadcasting**, enabling you to receive these updates via a callback function.

## Usage

To enable broadcasting, provide a **callback function** to the `broadcast_callback` parameter in `set_config`. This function will receive broadcasting updates:

```python
--8<-- "docs/scripts/broadcast.py:callback_creation"
```

With broadcasting enabled, call `rt.broadcast(...)` inside any function run in RT to invoke the handler.

```python
--8<-- "docs/scripts/broadcast.py:broadcast_call"
```

!!! warning
    Currently, only string messages can be broadcasted.


