# Broadcasting

Broadcasting lets you monitor your agents' progress in real time by sending live updates during execution. This can be useful for:

- Displaying progress in a UI or dashboard
- Logging intermediate steps for debugging
- Triggering alerts based on runtime events

Railtracks supports basic **data broadcasting**, enabling you to receive these updates via a callback function.

## Usage

To enable broadcasting, provide a **callback function** to the `broadcast_callback` parameter in `set_config`. This function will receive broadcasting updates:

```python
def example_broadcasting_handler(data):
    print(f"Received data: {data}")

rt.set_config(broadcast_callback=example_broadcasting_handler)
```

With broadcasting enabled, call `rt.broadcast(...)` inside any function run in RT to invoke the handler.

```python
@rt.function_node
async def example_node(data: list[str]):
    await rt.broadcast(f"Handling {len(data)} items")
```

Warning

Currently, only string messages can be broadcasted.
