"""Runnable snippets for the NodeBuilder advanced-usage doc.

`NodeBuilder` is the internal factory behind `rt.agent_node` / `rt.function_node`.
These snippets use its real surface (`model`, `system_message`, `schema`,
`connected_nodes`, `tool_details`, `tool_params`, `middleware`, `model_middleware`).
Each region is embedded via pymdownx.snippets.
"""

# --8<-- [start: llm_basic]
import railtracks as rt
from railtracks.built_nodes._node_builder import NodeBuilder

MyAgent = NodeBuilder.llm(
    name="MyAgent",
    model=rt.llm.OpenAILLM("gpt-4o"),
    system_message=rt.llm.SystemMessage("You are a helpful assistant."),
).build()
# --8<-- [end: llm_basic]


# --8<-- [start: llm_structured]
from pydantic import BaseModel


class Summary(BaseModel):
    title: str
    body: str


SummaryAgent = NodeBuilder.llm(
    name="SummaryAgent",
    model=rt.llm.OpenAILLM("gpt-4o"),
    schema=Summary,  # node now returns StructuredResponse[Summary]
).build()
# --8<-- [end: llm_structured]


# --8<-- [start: function_node]
from railtracks.llm import Parameter


async def fetch_weather(city: str) -> str:
    return f"Sunny in {city}"


WeatherNode = NodeBuilder.function(
    fetch_weather,
    name="fetch_weather",
    tool_details="Returns the current weather for a city.",
    tool_params=[Parameter(name="city", description="City name", param_type="string")],
).build()
# --8<-- [end: function_node]


# --8<-- [start: connected_tools]
SearchAgent = NodeBuilder.llm(
    name="SearchAgent",
    model=rt.llm.OpenAILLM("gpt-4o"),
    connected_nodes=[WeatherNode],  # tools this agent may call
).build()
# --8<-- [end: connected_tools]


# --8<-- [start: expose_as_tool]
TranslatorAgent = NodeBuilder.llm(
    name="Translator",
    model=rt.llm.OpenAILLM("gpt-4o"),
    system_message=rt.llm.SystemMessage("Translate the given text."),
    tool_details="Translates text from one language to another.",
    tool_params=[
        Parameter(name="text", description="Text to translate", param_type="string"),
        Parameter(
            name="target_language",
            description="Target language",
            param_type="string",
        ),
    ],
).build()
# --8<-- [end: expose_as_tool]


# --8<-- [start: middleware]
@rt.wrapper
async def retry(call, *args, **kwargs):
    for attempt in range(3):
        try:
            return await call(*args, **kwargs)
        except Exception:
            if attempt == 2:
                raise


ResilientAgent = NodeBuilder.llm(
    name="ResilientAgent",
    model=rt.llm.OpenAILLM("gpt-4o"),
    middleware=[retry],  # node boundary: once per agent run
    model_middleware=[retry],  # raw model call: once per model round-trip
).build()
# --8<-- [end: middleware]


# --8<-- [start: model_factory]
def pick_model():
    # Resolved fresh on every model call.
    return rt.llm.OpenAILLM(rt.context.get("model_name") or "gpt-4o-mini")


DynamicAgent = NodeBuilder.llm(name="DynamicAgent", model=pick_model).build()
# --8<-- [end: model_factory]


# --8<-- [start: context_injection]
# Injection is opt-in: without rt.middleware.ContextInjection() in
# model_middleware, {placeholders} are left untouched.
LiteralAgent = NodeBuilder.llm(
    name="LiteralAgent",
    model=rt.llm.OpenAILLM("gpt-4o"),
    system_message=rt.llm.SystemMessage("Use {curly braces} freely."),
).build()

InjectingAgent = NodeBuilder.llm(
    name="InjectingAgent",
    model=rt.llm.OpenAILLM("gpt-4o"),
    system_message=rt.llm.SystemMessage("You are helping {user_name}."),
    model_middleware=[rt.middleware.ContextInjection()],
).build()
# --8<-- [end: context_injection]
