# Web Search Tooling

A common need for an agent is to look things up on the live web. Railtracks provides a built-in web search tool you can drop into your agent right away.

## Usage

The default web-search backends rely on optional dependencies in the `websearch` extra, so install it before constructing `WebSearchToolSet`:

```bash
pip install "railtracks[websearch]"
# or
uv pip install "railtracks[websearch]"
```

This installs the default search and fetch dependencies (`tavily-python`, `httpx`, and `trafilatura`). Even if you swap in another backend such as `BraveSearch`, the fetch side still relies on the same HTTP/text-extraction packages, so the extra is still required.

Adding the web search tool to your agent is super easy.

```python
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
```

You will usually want to tell the agent how to use the tools in your prompt. We provide a helper that returns a ready-made guidance string:

```python
# the tool set provides a class method returning a prompt that guides the agent.
WebSearchToolSet.prompt()
```

## The Tools

The toolset exposes three tools to the agent:

| Tool                               | Purpose                                                                                                                                                        |
| ---------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `search(query, top_k=5)`           | Search the web and return ranked title, url, and snippet results.                                                                                              |
| `fetch(url)`                       | Fetch a url, usually one from `search()`, and return its cleaned page text.                                                                                    |
| `search_and_fetch(query, top_k=3)` | Search and fetch full content for the top results in a single call. Convenient when you want full page content right away, at the cost of fetching more pages. |

If a search or fetch fails (a backend outage, a blocked or paywalled page, no extractable content), the tool returns a plain message describing the failure instead of raising, so the agent can see what happened and try something else.

## Swapping the search backend

By default the toolset uses `TavilySearch`, so it needs a `TAVILY_API_KEY`. You can swap in a different backend, for example `BraveSearch`, which needs a `BRAVE_API_KEY` instead:

```python
import railtracks as rt
from railtracks.prebuilt.tools.websearch.search import BraveSearch

# swap Tavily for Brave, only requires setting BRAVE_API_KEY
web_search = WebSearchToolSet(search=BraveSearch())
```

Any object that implements the `SearchBackend` protocol, an async `search(query, top_k)` method returning a list of results, can be passed in, so you can bring your own backend too.

## Swapping the fetch backend

By default the toolset uses `HttpFetch`, a plain HTTP request paired with `trafilatura` to extract clean text from the page. You can tune it, or swap in your own implementation of the `FetchBackend` protocol, for example to use a headless browser for JavaScript-heavy pages:

```python
import railtracks as rt
from railtracks.prebuilt.tools.websearch.fetch import HttpFetch

# tune the default fetch backend, e.g. a longer timeout for slow pages
web_search = WebSearchToolSet(fetch=HttpFetch(timeout=30.0))
```
