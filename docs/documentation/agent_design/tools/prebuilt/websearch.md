# Web Search Tooling

A common need for an agent is to look things up on the live web. Railtracks provides a built-in web search tool you can drop into your agent right away.

## Usage
Adding the web search tool to your agent is super easy.

```python
--8<-- "docs/scripts/websearch.py:websearch"
```

You will usually want to tell the agent how to use the tools in your prompt. We provide a helper that returns a ready-made guidance string:

```python
--8<-- "docs/scripts/websearch.py:websearch_prompt"
```

## The Tools

The toolset exposes three tools to the agent:

| Tool | Purpose |
|---|---|
| `search(query, top_k=5)` | Search the web and return ranked title, url, and snippet results. |
| `fetch(url)` | Fetch a url, usually one from `search()`, and return its cleaned page text. |
| `search_and_fetch(query, top_k=3)` | Search and fetch full content for the top results in a single call. Convenient when you want full page content right away, at the cost of fetching more pages. |

If a search or fetch fails (a backend outage, a blocked or paywalled page, no extractable content), the tool returns a plain message describing the failure instead of raising, so the agent can see what happened and try something else.

## Swapping the search backend

By default the toolset uses `TavilySearch`, so it needs a `TAVILY_API_KEY`. You can swap in a different backend, for example `BraveSearch`, which needs a `BRAVE_API_KEY` instead:

```python
--8<-- "docs/scripts/websearch.py:websearch_search_backend"
```

Any object that implements the `SearchBackend` protocol, an async `search(query, top_k)` method returning a list of results, can be passed in, so you can bring your own backend too.

## Swapping the fetch backend

By default the toolset uses `HttpFetch`, a plain HTTP request paired with `trafilatura` to extract clean text from the page. You can tune it, or swap in your own implementation of the `FetchBackend` protocol, for example to use a headless browser for JavaScript-heavy pages:

```python
--8<-- "docs/scripts/websearch.py:websearch_fetch_backend"
```
