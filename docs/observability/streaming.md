# 🚰 Streaming

Streaming lets you monitor your agents' progress in real time by sending live updates during execution. This can be useful for:

- Displaying progress in a UI or dashboard
- Logging intermediate steps for debugging
- Triggering alerts based on runtime events

Railtracks supports basic **data streaming**, enabling you to receive these updates via a callback function.

## ⚙️ Usage

To enable streaming, provide a **callback function** to the `subscriber` parameter in `ExecutorConfig`. This function will receive streaming updates:

```python
import railtracks as rt

def example_streaming_handler(data):
    print(f"Received data: {data}")

rt.ExecutorConfig(subscriber=example_streaming_handler)
```

With streaming enabled, call `rt.stream(...)` inside any function decorated with `@rt.to_node` to send updates:

```python
import railtracks as rt

@rt.to_node
def example_node(data: list[str]):
    rt.stream(f"Handling {len(data)} items")
```

!!! tip "💡 Note"
    Currently, only string messages can be streamed.


