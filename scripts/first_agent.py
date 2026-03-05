from ast import Str
import asyncio

# --8<-- [start: imports]
import railtracks as rt
from pydantic import BaseModel
# --8<-- [end: imports]

# --8<-- [start: simple_llm]
SimpleLLM = rt.agent_node(
    llm=rt.llm.AnthropicLLM("claude-sonnet-4-20250514"),
    system_message="You are a helpful AI assistant."
)
# --8<-- [end: simple_llm]

# --8<-- [start: general_structured]
from pydantic import BaseModel, Field

class YourModel(BaseModel):
    # Use the Field parameter for more control. 
    parameter: str = Field(default="default_value", description="Your description of the parameter")
# --8<-- [end: general_structured]

# --8<-- [start: weather_response]
class WeatherResponse(BaseModel):
    temperature: float
    condition: str
# --8<-- [end: weather_response]

# --8<--- [start: general_tool]
# Use @rt.function_node decorator to convert your function into a RT tool
@rt.function_node
def your_function(example_input: str):
    """
    Your function description here.

    Args:
      example_input (str): The input string to process.

    """
    pass
# --8<--- [end: general_tool]

# --8<-- [start: weather_tool]
@rt.function_node
def weather_tool(city: str):
    """
    Returns the current weather for a given city.

    Args:
      city (str): The name of the city to get the weather for.
    """
    # Simulate a weather API call
    return f"{city} is sunny with a temperature of 25°C."
# --8<-- [end: weather_tool]

# --8<-- [start: first_agent_tools]
WeatherAgent = rt.agent_node(
    name="Weather Agent",
    llm=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You are a helpful assistant that answers weather-related questions.",
    tool_nodes=[weather_tool],
)
# --8<-- [end: first_agent_tools]

# --8<-- [start: first_agent_model]
StructuredWeatherAgent = rt.agent_node(
    name="Weather Agent",
    llm=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You are a helpful assistant that answers weather-related questions.",
    output_schema=WeatherResponse,
)
# --8<-- [end: first_agent_model]

# --8<-- [start: first_agent_all]
StructuredToolCallWeatherAgent = rt.agent_node(
    name="Weather Agent",
    llm=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You are a helpful assistant that answers weather-related questions.",
    tool_nodes=[weather_tool],
    output_schema=WeatherResponse,
)
# --8<-- [end: first_agent_all]

# --8<-- [start: call]
async def weather_agent():
    response = await rt.call(
        StructuredToolCallWeatherAgent, 
        "What is the forecast for Vancouver today?"
        )
    return response
# --8<-- [end: call]

# --8<-- [start: dynamic_prompts]
system_message = rt.llm.SystemMessage(
    "You can also geolocate the user"
)
user_message = rt.llm.UserMessage(
    "Would you please be able to tell me the forecast for the next week?"
)
async def main():

    response = await rt.call(
        StructuredToolCallWeatherAgent,
        user_input=rt.llm.MessageHistory([system_message, user_message]),
        llm=rt.llm.AnthropicLLM("claude-3-5-sonnet-20241022"),
    )

    return response
# --8<-- [end: dynamic_prompts]
response = asyncio.run(main())
print(response.structured.temperature)

# --8<-- [start: fewshot]
async def few_shot():
    response = await rt.call(
        WeatherAgent,
        [
            rt.llm.UserMessage("What is the forecast for BC today?"),
            rt.llm.AssistantMessage("Please specify the specific city in BC you're interested in"),
            rt.llm.UserMessage("Vancouver"),
        ]
    )
    return response

# --8<-- [end: fewshot]
weather_context: dict[str, str] = {}
# --8<-- [start: session]
async def session_based():
    with rt.Session(
        context=weather_context,
        timeout=60  # seconds
    ):
        response = await rt.call(
            WeatherAgent,
            "What is the weather like in Vancouver?"
        )
# --8<-- [end: session]
