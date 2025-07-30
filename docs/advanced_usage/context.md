# 🌍 Global Context

RailTracks includes a concept of global context, letting you store and retrieve shared information across the lifecycle of a run. This makes it easy to coordinate data like config settings, environment flags, or shared resources.

## 🧠 What is Global Context?

The context system gives you a simple and clear API for interacting with shared values. It's scoped to the duration of a run, so everything is neatly contained.

## 🧰 Core Functions

You can use the context with just two main functions:

* `rt.context.get(key, default=None)`
* `rt.context.put(key, value)`

## 🚀 Quick Example

Here’s how you can use context during a run:

```python
import railtracks as rt

# Set up some context data
data = {"var_1": "value_1"}

with rt.Session(context=data):
    rt.context.get("var_1")  # ➡️ Outputs: value_1
    rt.context.get("var_2", "default_value")  # ➡️ Outputs: default_value

    rt.context.put("var_2", "value_2")  # Sets var_2 to value_2
    rt.context.put("var_1", "new_value_1")  # Replaces var_1 with new_value_1
```

!!! tip
    You can also use context inside nodes:
    
    ```python
    import railtracks as rt
    
    @rt.to_node
    def some_node():
        return rt.context.get("var_1")
    
    with rt.Runner(context={"var_1": "value_1"}):
        rt.call_sync(some_node)
    ```

!!! warning
    The context only exists while the run is active. After that, it's gone.

## 🧪 Real-World Example

Say multiple parts of your code need access to something like an `API_KEY`. You can stash it in the context and reuse it without passing it around explicitly:

```python
import railtracks as rt
import os

api_key = os.environ["API_KEY"]


def api_call_1():
    key = rt.context.get("api_key")
    # Use the key...


def api_call_2():
    key = rt.context.get("api_key")
    # Use the key...


with rt.Session(context={"api_key": api_key}):
    rt.call_sync(api_call_1)
    rt.call_sync(api_call_2)
```

This approach reduces repetitive code and keeps sensitive info out of LLM inputs.

!!! note
    You could use global variables, but the context system gives you a safer and clearer way to manage shared values. It makes your runs more predictable and your data easier to reason about. ✅

