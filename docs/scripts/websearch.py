# --8<-- [start: websearch]
import railtracks as rt

# create your web search toolset (defaults to Tavily for search, httpx + trafilatura for fetch)
web_search = rt.prebuilt.WebSearchToolSet()

agent = rt.agent_node(
    name="Research Agent",
    tool_nodes=[*web_search.tool_set()],  # the tools your agent can call
    llm=rt.llm.OpenAILLM("gpt-4o"),
    system_message=rt.prebuilt.WebSearchToolSet.prompt(),
)
# --8<-- [end: websearch]

# --8<-- [start: websearch_prompt]
# the tool set provides a class method returning a prompt that guides the agent.
rt.prebuilt.WebSearchToolSet.prompt()
# --8<-- [end: websearch_prompt]

# --8<-- [start: websearch_search_backend]
import railtracks as rt
from railtracks.prebuilt.tools.websearch.search import BraveSearch

# swap Tavily for Brave, only requires setting BRAVE_API_KEY
web_search = rt.prebuilt.WebSearchToolSet(search=BraveSearch())
# --8<-- [end: websearch_search_backend]

# --8<-- [start: websearch_fetch_backend]
import railtracks as rt
from railtracks.prebuilt.tools.websearch.fetch import HttpFetch

# tune the default fetch backend, e.g. a longer timeout for slow pages
web_search = rt.prebuilt.WebSearchToolSet(fetch=HttpFetch(timeout=30.0))
# --8<-- [end: websearch_fetch_backend]
