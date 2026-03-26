import os

import railtracks as rt
from pydantic import BaseModel
from rich import print
from tavily import TavilyClient

# rt.enable_logging() # uncomment for detailed logs

#### API Key Setup #####
"""
1. Create a .env file in the root of your project
2. Add the following lines to your .env file:
TAVILY_API_KEY="your_tavily_api_key_here"
GEMINI_API_KEY="your_gemini_api_key_here"
"""

##### Tool Definition #####
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

@rt.function_node
def web_search(query: str) -> str:
    """Performs a web search using the Tavily API and returns the results.

    Args:
        query (str): The search query string.
    """
    response = tavily_client.search(query)
    return response["results"]


#### Data Models #####
class Person(BaseModel):
    first_name: str
    last_name: str


class Cast(BaseModel):
    cast: list[Person]


class Link(BaseModel):
    imdb_link: str


##### Agent Definitions #####
XRAY_agent = rt.agent_node(
    name="Prime Video Agent",
    system_message="You recognize actors and actresses in a given photo",
    llm=rt.llm.GeminiLLM("gemini-3-flash-preview"),
    output_schema=Cast,
)

IMDB_agent = rt.agent_node(
    name="IMDB Agent",
    system_message="You find IMDB profiles given actors or actresses names",
    llm=rt.llm.GeminiLLM("gemini-3-flash-preview"),
    tool_nodes=[web_search],
    output_schema=Link,
)

##### Define the Agentic Architecture #####
@rt.function_node
async def main(path: str) -> list[str]:
    """Flow entry to process the image and return IMDB links of the people in the photo.

    Args:
        path (str): The file path to the image to be processed.
    Returns:
        list[str]: A list of IMDB profile links for the people identified in the photo.
    """

    # Create a user message with the image attachment for the XRAY agent
    message = rt.llm.UserMessage(
        content="Who are the people in this photo?", attachment=path
    )

    # Invoking the XRAY agent to identify the people in the photo
    resp = await rt.call(XRAY_agent, message)

    links = []

    # For each person identified by the XRAY agent, call the IMDB agent to find their IMDB profile link
    for person in resp.structured.cast:
        imdb_resp = await rt.call(IMDB_agent, f"Find the IMDB Profile of {person}")
        links.append(imdb_resp.structured.imdb_link)

    return links


#### Flow Definition #####
pv_flow = rt.Flow(
    name="Prime Video Flow", entry_point=main
)  # `main` function as the entry point of the flow

if __name__ == "__main__":
    image_path = "https://tinyurl.com/2nbpr9v3"  # Replace with the path to your image (URL or local path)
    result = pv_flow.invoke(image_path)
    print(result)
