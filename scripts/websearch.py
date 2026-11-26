# --8<-- [start: websearch]
import railtracks as rt
from railtracks.prebuilt.tools.websearch import WebSearchToolSet

# create your web search toolset (defaults to Tavily for search, httpx + trafilatura for fetch)
web_search = WebSearchToolSet()

ResearchAgent = rt.agent_node(
    name="Research Agent",
    tool_nodes=[*web_search.tool_set()],  # the tools your agent can call
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
    system_message=WebSearchToolSet.prompt(),
)
# --8<-- [end: websearch]

# --8<-- [start: websearch_prompt]
# the tool set provides a class method returning a prompt that guides the agent.
WebSearchToolSet.prompt()
# --8<-- [end: websearch_prompt]

# --8<-- [start: websearch_search_backend]
import railtracks as rt
from railtracks.prebuilt.tools.websearch.search import BraveSearch

# swap Tavily for Brave, only requires setting BRAVE_API_KEY
web_search = WebSearchToolSet(search=BraveSearch())
# --8<-- [end: websearch_search_backend]

# --8<-- [start: websearch_fetch_backend]
import railtracks as rt
from railtracks.prebuilt.tools.websearch.fetch import HttpFetch

# tune the default fetch backend, e.g. a longer timeout for slow pages
web_search = WebSearchToolSet(fetch=HttpFetch(timeout=30.0))
# --8<-- [end: websearch_fetch_backend]

# --8<-- [start: websearch_allowed_hosts]
import litellm

# let the default fetch backend read an internal host (process-wide)
litellm.user_url_allowed_hosts = ["wiki.internal:8080"]
# --8<-- [end: websearch_allowed_hosts]

# --8<-- [start: websearch_custom_fetch]
from urllib.parse import urlparse

from railtracks.prebuilt.tools.websearch import FetchResult


class AllowListFetch:
    """Fetch pages only from hosts your app allows."""

    def __init__(self, allowed_hosts: set[str]) -> None:
        self._allowed_hosts = allowed_hosts
        self._fetch = HttpFetch()

    async def fetch(self, url: str) -> FetchResult:
        if urlparse(url).hostname not in self._allowed_hosts:
            return FetchResult(
                url=url, is_error=True, error_message="This host is not allowed."
            )
        return await self._fetch.fetch(url)


web_search = WebSearchToolSet(fetch=AllowListFetch({"docs.python.org"}))
# --8<-- [end: websearch_custom_fetch]
