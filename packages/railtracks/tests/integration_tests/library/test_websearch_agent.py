import pytest
import railtracks as rt
from railtracks.llm import ToolCall
from railtracks.prebuilt.tools.websearch import WebSearchToolSet
from railtracks.prebuilt.tools.websearch.models import FetchResult, SearchResult


class _FakeSearch:
    def __init__(self, results):
        self._results = results

    async def search(self, query, *, top_k=5):
        return self._results


class _FakeFetch:
    def __init__(self, result):
        self._result = result

    async def fetch(self, url):
        return self._result


class TestWebSearchToolCalling:
    @pytest.mark.asyncio
    async def test_search_tool_round_trips_through_agent(self, mock_llm):
        results = [
            SearchResult(
                title="Railtracks",
                url="https://railtracks.org",
                snippet="An agentic framework",
            )
        ]
        toolset = WebSearchToolSet(search=_FakeSearch(results), fetch=_FakeFetch(None))

        llm = mock_llm(
            requested_tool_calls=[
                ToolCall(
                    name="search",
                    identifier="id_search_1",
                    arguments={"query": "railtracks framework"},
                )
            ]
        )

        agent = rt.agent_node(
            tool_nodes=toolset.tool_set(),
            name="Web Research Agent",
            system_message=WebSearchToolSet.prompt(),
            llm=llm,
        )

        with rt.Session():
            response = await rt.call(agent, user_input="What is railtracks?")
            assert "An agentic framework" in response.text
            assert "https://railtracks.org" in response.text

    @pytest.mark.asyncio
    async def test_fetch_tool_round_trips_through_agent(self, mock_llm):
        fetch_result = FetchResult(
            url="https://railtracks.org",
            title="Railtracks",
            text="Full page content here",
        )
        toolset = WebSearchToolSet(
            search=_FakeSearch([]), fetch=_FakeFetch(fetch_result)
        )

        llm = mock_llm(
            requested_tool_calls=[
                ToolCall(
                    name="fetch",
                    identifier="id_fetch_1",
                    arguments={"url": "https://railtracks.org"},
                )
            ]
        )

        agent = rt.agent_node(
            tool_nodes=toolset.tool_set(),
            name="Web Research Agent",
            system_message=WebSearchToolSet.prompt(),
            llm=llm,
        )

        with rt.Session():
            response = await rt.call(agent, user_input="Read https://railtracks.org")
            assert "Full page content here" in response.text
