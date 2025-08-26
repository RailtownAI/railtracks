import asyncio

# --8<-- [start: imports]
import railtracks as rt
from pydantic import BaseModel
# --8<-- [end: imports]

# --8<-- [start: weather_response]
class WeatherResponse(BaseModel):
    temperature: float
    condition: str
# --8<-- [end: weather_response]

# --8<-- [start: weather_tool]
def weather_tool(city: str):
    """
    Returns the current weather for a given city.

    Args:
      city (str): The name of the city to get the weather for.
    """
    # Simulate a weather API call
    return f"{city} is sunny with a temperature of 25°C."
# --8<-- [end: weather_tool]

# --8<-- [start: first_agent]
WeatherAgent = rt.agent_node(
    name="Weather Agent",
    llm_model=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You are a helpful assistant that answers weather-related questions.",
    tool_nodes=[rt.function_node(weather_tool)],
    output_schema=WeatherResponse,
)
# --8<-- [end: first_agent]

# --8<-- [start: call]
async def main():
    response = await rt.call(
        WeatherAgent, 
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
async def top_level():

    response = await rt.call(
        WeatherAgent,
        user_input=rt.llm.MessageHistory([system_message, user_message]),
        llm_model=rt.llm.AnthropicLLM("claude-3-5-sonnet-20241022"),
    )

    return response
# --8<-- [end: dynamic_prompts]
response = asyncio.run(top_level())
print(response.structured.temperature)

# --8<-- [start: fewshot]
async def top_level():
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
weather_context = {}
# --8<-- [start: session]
async def top_level():
    with rt.Session(
        context=weather_context,
        timeout=60  # seconds
    ):
        response = await rt.call(
            WeatherAgent,
            "What is the weather like in Vancouver?"
        )
# --8<-- [end: session]
