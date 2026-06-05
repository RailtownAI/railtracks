# Custom Node Creation with NodeBuilder

`NodeBuilder` is the low-level factory for creating LLM agent nodes and function nodes. `rt.agent_node` and `rt.function_node` are thin wrappers around it — use `NodeBuilder` directly when you need control over middleware, gateway configuration, or tool exposure that those helpers don't expose.

---

## LLM nodes — `NodeBuilder.llm()`

```python
import railtracks as rt
from railtracks.built_nodes._node_builder import NodeBuilder
from railtracks.built_nodes.llm_helpers import Gateway

MyAgent = NodeBuilder.llm(
    name="MyAgent",                          # node name (also used as tool name if exposed as a tool)
    gateway=Gateway(rt.llm.OpenAILLM("gpt-4o")),
    system_message=rt.llm.SystemMessage("You are a helpful assistant."),
).build()
```

### Structured output

Pass a Pydantic model to `schema` and the node returns `StructuredResponse[YourModel]` instead of `StringResponse`:

```python
from pydantic import BaseModel

class Summary(BaseModel):
    title: str
    body: str

SummaryAgent = NodeBuilder.llm(
    name="SummaryAgent",
    gateway=Gateway(rt.llm.OpenAILLM("gpt-4o")),
    schema=Summary,
).build()
```

### Connected tools

```python
SearchAgent = NodeBuilder.llm(
    name="SearchAgent",
    gateway=Gateway(rt.llm.OpenAILLM("gpt-4o")),
    connected_nodes=[SearchNode, LookupNode],
).build()
```

### Exposing a node as a tool

Pass `tool_details` and `tool_params` to make the node callable as a tool from other agents:

```python
from railtracks.llm import Parameter

TranslatorAgent = NodeBuilder.llm(
    name="Translator",
    gateway=Gateway(rt.llm.OpenAILLM("gpt-4o")),
    system_message=rt.llm.SystemMessage("Translate the given text."),
    tool_details="Translates text from one language to another.",
    tool_params=[
        Parameter(name="text", description="Text to translate", param_type="string"),
        Parameter(name="target_language", description="Target language", param_type="string"),
    ],
).build()
```

---

## Function nodes — `NodeBuilder.function()`

Wraps any async function as a node:

```python
async def fetch_weather(city: str) -> str:
    return f"Sunny in {city}"

WeatherNode = NodeBuilder.function(
    fetch_weather,
    name="fetch_weather",
    tool_details="Returns the current weather for a city.",
    tool_params=[Parameter(name="city", description="City name", param_type="string")],
).build()
```

Sync functions are not supported directly — wrap them with `asyncio.to_thread` first.

---

## Node-level middleware

Both `NodeBuilder.llm()` and `NodeBuilder.function()` accept the same middleware parameters. These run around `wrapped_invoke`, the node's outer execution boundary:

| Parameter | Type | Description |
|---|---|---|
| `wrappers` | `list[Wrapper]` | Decorators applied to `invoke` (retry, auth, tracing) |
| `input_maps` | `list[MapInputs]` | Transform `*args, **kwargs` before `invoke` |
| `output_maps` | `list[MapOutputs]` | Transform the return value after `invoke` |

```python
from railtracks.nodes.wrappers import Wrapper

async def retry_wrapper(fn):
    async def wrapped(*args, **kwargs):
        for attempt in range(3):
            try:
                return await fn(*args, **kwargs)
            except Exception:
                if attempt == 2:
                    raise
    return wrapped

MyAgent = NodeBuilder.llm(
    name="ResilientAgent",
    gateway=Gateway(rt.llm.OpenAILLM("gpt-4o")),
    wrappers=[retry_wrapper],
).build()
```

---

## Gateway middleware — `Gateway` and `GatewayManager`

`Gateway` manages the LLM invocation itself. It accepts its own middleware stack that runs *inside* the node, around the raw model call:

| Parameter | Type | Description |
|---|---|---|
| `wrappers` | `list[GatewayWrapper]` | Wraps the model call (rate limiting, fallback, logging) |
| `pre_mappers` | `list[GatewayPreMapper] \| GatewayManager` | Transform `(messages, schema, tools)` before the model call |
| `post_mappers` | `list[GatewayPostMapper]` | Transform the model response after the call |

```python
from railtracks.built_nodes.llm_helpers import Gateway
from railtracks.built_nodes.gateway_types import GatewayPreMapper

async def redact_pii(messages, schema, tools):
    # scrub messages before they reach the model
    ...
    return messages, schema, tools

MyAgent = NodeBuilder.llm(
    name="SafeAgent",
    gateway=Gateway(
        rt.llm.OpenAILLM("gpt-4o"),
        pre_mappers=[redact_pii],
    ),
).build()
```

### GatewayManager

When you pass a list to `pre_mappers`, `Gateway` wraps it in a `GatewayManager` internally. You can also construct one explicitly if you want to inspect or compose mapper lists before passing them:

```python
from railtracks.built_nodes.gateway_manager import GatewayManager

my_mappers = GatewayManager([redact_pii, my_logger])

MyAgent = NodeBuilder.llm(
    name="SafeAgent",
    gateway=Gateway(rt.llm.OpenAILLM("gpt-4o"), pre_mappers=my_mappers),
).build()
```

Iterating over a `GatewayManager` yields only the user-provided mappers — system-registered mappers (such as context injection) are stored in separate internal layers and are never visible through the public interface. `GatewayManager.from_user_input()` always produces a fresh copy, so your original list or manager is never modified.

---

## Context injection

Context injection (filling `{placeholder}` templates from `rt.context`) is enabled by default for all LLM nodes. Disable it per-node with `context_injection=False`:

```python
MyAgent = NodeBuilder.llm(
    name="LiteralAgent",
    gateway=Gateway(rt.llm.OpenAILLM("gpt-4o")),
    system_message=rt.llm.SystemMessage("Use {curly braces} freely."),
    context_injection=False,
).build()
```

See the [Context Injection walkthrough](../tutorials/walkthroughs/prompts_and_context.md) for the full four-level control hierarchy.
