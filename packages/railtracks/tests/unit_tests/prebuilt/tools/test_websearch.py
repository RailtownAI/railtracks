import re

import pytest
from railtracks.prebuilt.tools.websearch import WebSearchToolSet
from railtracks.prebuilt.tools.websearch.fetch import HttpFetch
from railtracks.prebuilt.tools.websearch.models import FetchResult, SearchResult
from railtracks.prebuilt.tools.websearch.search import TavilySearch


def _contains_url(text: str, url: str) -> bool:
    """Check that `url` appears in `text` as a whole token.

    A plain `url in text` substring check would also match a spoofed
    superstring like "https://a.com.evil.com", so anchor on a non-URL
    character (or end of string) right after it.
    """
    return re.search(rf"{re.escape(url)}(?![\w./-])", text) is not None


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeSearch:
    def __init__(self, results=None, raise_error=False):
        self._results = results or []
        self._raise_error = raise_error

    async def search(self, query, *, top_k=5):
        if self._raise_error:
            raise RuntimeError("search backend boom")
        return self._results[:top_k]


class _FakeFetch:
    def __init__(self, result=None, raise_error=False):
        self._result = result
        self._raise_error = raise_error

    async def fetch(self, url):
        if self._raise_error:
            raise RuntimeError("fetch backend boom")
        return self._result or FetchResult(url=url, text="default text")


@pytest.fixture
def ts():
    return WebSearchToolSet(search=_FakeSearch(), fetch=_FakeFetch())


# ---------------------------------------------------------------------------
# search()
# ---------------------------------------------------------------------------


async def test_search_formats_results():
    results = [
        SearchResult(title="A", url="https://a.com", snippet="snip a"),
        SearchResult(title="B", url="https://b.com", snippet="snip b"),
    ]
    ts = WebSearchToolSet(search=_FakeSearch(results=results), fetch=_FakeFetch())
    out = await ts.search("query")
    assert "A — https://a.com" in out
    assert "snip a" in out
    assert "B — https://b.com" in out


async def test_search_empty_results():
    ts = WebSearchToolSet(search=_FakeSearch(results=[]), fetch=_FakeFetch())
    out = await ts.search("nothing")
    assert "No results found" in out
    assert "nothing" in out


async def test_search_backend_exception_is_caught():
    ts = WebSearchToolSet(search=_FakeSearch(raise_error=True), fetch=_FakeFetch())
    out = await ts.search("query")
    assert "Search failed" in out


# ---------------------------------------------------------------------------
# fetch()
# ---------------------------------------------------------------------------


async def test_fetch_returns_cleaned_text_with_title():
    result = FetchResult(url="https://a.com", title="A Page", text="body text")
    ts = WebSearchToolSet(search=_FakeSearch(), fetch=_FakeFetch(result=result))
    out = await ts.fetch("https://a.com")
    assert "A Page" in out
    assert "body text" in out


async def test_fetch_is_error_reports_message():
    result = FetchResult(url="https://a.com", is_error=True, error_message="blocked")
    ts = WebSearchToolSet(search=_FakeSearch(), fetch=_FakeFetch(result=result))
    out = await ts.fetch("https://a.com")
    assert "Fetch failed" in out
    assert "blocked" in out


async def test_fetch_backend_exception_is_caught():
    ts = WebSearchToolSet(search=_FakeSearch(), fetch=_FakeFetch(raise_error=True))
    out = await ts.fetch("https://a.com")
    assert "Fetch failed" in out


# ---------------------------------------------------------------------------
# search_and_fetch()
# ---------------------------------------------------------------------------


async def test_search_and_fetch_combines_both():
    results = [SearchResult(title="A", url="https://a.com", snippet="snip a")]
    fetch_result = FetchResult(url="https://a.com", text="full content")
    ts = WebSearchToolSet(
        search=_FakeSearch(results=results), fetch=_FakeFetch(result=fetch_result)
    )
    out = await ts.search_and_fetch("query")
    assert "A" in out
    assert _contains_url(out, "https://a.com")
    assert "full content" in out


async def test_search_and_fetch_empty_results():
    ts = WebSearchToolSet(search=_FakeSearch(results=[]), fetch=_FakeFetch())
    out = await ts.search_and_fetch("nothing")
    assert "No results found" in out


async def test_search_and_fetch_partial_failure_does_not_abort():
    class _MixedFetch:
        async def fetch(self, url):
            if url == "https://fail.com":
                return FetchResult(url=url, is_error=True, error_message="blocked")
            return FetchResult(url=url, text="good content")

    results = [
        SearchResult(title="Bad", url="https://fail.com", snippet="s"),
        SearchResult(title="Good", url="https://ok.com", snippet="s"),
    ]
    ts = WebSearchToolSet(search=_FakeSearch(results=results), fetch=_MixedFetch())
    out = await ts.search_and_fetch("query", top_k=2)
    assert "[fetch failed: blocked]" in out
    assert "good content" in out


async def test_search_and_fetch_search_backend_exception_is_caught():
    ts = WebSearchToolSet(search=_FakeSearch(raise_error=True), fetch=_FakeFetch())
    out = await ts.search_and_fetch("query")
    assert "Search failed" in out


# ---------------------------------------------------------------------------
# Backend injection / defaults
# ---------------------------------------------------------------------------


async def test_injected_backends_are_used(ts):
    assert isinstance(ts.search_backend, _FakeSearch)
    assert isinstance(ts.fetch_backend, _FakeFetch)


def test_defaults_to_tavily_and_http_fetch(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "dummy-key")
    ts = WebSearchToolSet()
    assert isinstance(ts.search_backend, TavilySearch)
    assert isinstance(ts.fetch_backend, HttpFetch)


# ---------------------------------------------------------------------------
# tool_set() / prompt()
# ---------------------------------------------------------------------------


def test_tool_set_returns_rt_functions(ts):
    tools = ts.tool_set()
    assert len(tools) == 3
    assert all(hasattr(t, "node_type") for t in tools)


async def test_tool_set_bound_to_instance():
    results = [SearchResult(title="A", url="https://a.com", snippet="s")]
    ts = WebSearchToolSet(search=_FakeSearch(results=results), fetch=_FakeFetch())
    search_tool = ts.tool_set()[0]
    out = await search_tool("query")
    assert "A" in out


def test_prompt_is_non_empty_string():
    result = WebSearchToolSet.prompt()
    assert isinstance(result, str)
    assert len(result) > 0
