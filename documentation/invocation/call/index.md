# Direct Invocation

**Direct invocation** is calling a node yourself with `await rt.call(...)` instead of letting an agent decide to call it. It is how the steps inside a [Flow](https://docs.railtracks.org/documentation/invocation/flows/index.md) are composed: when a Flow's [entry point](https://docs.railtracks.org/documentation/invocation/flows/#entry-point) is a function node, each step inside it is an `rt.call` whose result you use like any other awaited value.

```python
import railtracks as rt

resp = await rt.call(AgentName, "user message to the agent")
```

Because these are ordinary `await` expressions, the control flow stays yours. Await them one after another to fix an order (see [Sequential Flows](https://docs.railtracks.org/tutorials/concepts/architectures/sequential/index.md)), gather them with `asyncio.gather` to run steps concurrently, or branch on a result before deciding what to call next.

async context

The above code snippet will work in an `async` context such as Jupyter notebooks. In a python script, it needs to be wrapped as follows:

```python
from asyncio import run
import railtracks as rt

async def outer_func(...):
    resp = await rt.call(AgentName, "user message to the agent")

run(outer_func(...))
```

The `call` API is also useful when you want to use agents as tools by having them wrapped within another a function (see [Agents as Tools](https://docs.railtracks.org/documentation/agent_design/tools/agents_as_tools/index.md)).

Start from a Flow

`rt.call` does work as the top level of a script, where Railtracks builds the surrounding machinery for you with default settings. What you give up is everything that is configured on the Flow: a starting context copied into every run, `timeout`, `end_on_error`, broadcast and payload callbacks, and the `flow.connect()` handle for inspecting a [run](https://docs.railtracks.org/documentation/invocation/flows/#run) after it finishes. Past a quick experiment, wrap your entry point in a [Flow](https://docs.railtracks.org/documentation/invocation/flows/index.md) and keep `rt.call` for the steps inside it.

To continue a conversation across calls, see [Message History](https://docs.railtracks.org/documentation/invocation/message_history/index.md).
