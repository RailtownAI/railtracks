# --8<-- [start: direct]
import railtracks as rt

WeatherAgent = rt.agent_node(
    "Weather Agent",
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
    system_message="You find the current weather and forecast for a city.",
)

Assistant = rt.agent_node(
    "Assistant",
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
    system_message="You are a general assistant.",
    tool_nodes=[WeatherAgent],
)
# --8<-- [end: direct]

# --8<-- [start: manifest]
ManifestWeatherAgent = rt.agent_node(
    "Weather Agent",
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
    system_message="You find the current weather and forecast for a city.",
    manifest=rt.ToolManifest(
        description="Gets the current weather and forecast for a city.",
        parameters=[
            rt.llm.Parameter(
                name="city",
                description="The city to look up.",
                param_type="string",
            ),
        ],
    ),
)
# --8<-- [end: manifest]


# --8<-- [start: function]
@rt.function_node
async def weather_report(city: str, units: str) -> str:
    """Get a short weather report for a city.

    Args:
        city: The city to report on.
        units: Either "metric" or "imperial".
    """
    response = await rt.call(WeatherAgent, f"Weather in {city}, in {units} units.")
    return response.content


FunctionAssistant = rt.agent_node(
    "Assistant",
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
    system_message="You are a general assistant.",
    tool_nodes=[weather_report],
)
# --8<-- [end: function]
