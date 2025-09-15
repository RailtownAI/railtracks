# Broadcasting

Broadcasting lets you monitor your agents' progress in real time by sending live updates during execution. This can be useful for:

- Displaying progress in a UI or dashboard
- Logging intermediate steps for debugging
- Triggering alerts based on runtime events

Railtracks supports basic **data broadcasting**, enabling you to receive these updates via a callback function.

## Usage

To enable broadcasting, provide a **callback function** to the `subscriber` parameter in `ExecutorConfig`. This function will receive broadcasting updates:

```python
import railtracks as rt


def example_broadcasting_handler(data):
    print(f"Received data: {data}")


rt.ExecutorConfig(broadcast_callback=example_broadcasting_handler)
```

With broadcasting enabled, call `rt.broadcast(...)` inside any function decorated with `@rt.to_node` to send updates:

```python
import railtracks as rt


@rt.function_node
def example_node(data: list[str]):
    rt.broadcast(f"Handling {len(data)} items")
```

!!! warning
    Currently, only string messages can be broadcasted.


