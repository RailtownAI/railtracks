# --8<-- [start: parallel_search_mcp]
import json
import uuid

import railtracks as rt

# Free, keyless endpoint. Anonymous use has lower rate limits than an API key.
PARALLEL_SEARCH_MCP_URL = "https://search.parallel.ai/mcp"

# The same id on every call lets the server apply free-tier rate limiting per session.
session_id = uuid.uuid4().hex


def result_text(result) -> str:
    """Return the text of an MCP tool result."""
    return "\n".join(
        block.text for block in result.content if getattr(block, "type", "") == "text"
    )


def main() -> None:
    config = rt.MCPHttpParams(
        url=PARALLEL_SEARCH_MCP_URL,
        headers={"User-Agent": f"railtracks/{rt.__version__}"},
    )

    # The context manager closes the MCP connection when the block exits.
    with rt.connect_mcp(config) as server:
        tools = {tool.name(): tool for tool in server.tools}
        web_search = tools["web_search"]
        web_fetch = tools["web_fetch"]

        search_flow = rt.Flow("parallel-web-search", entry_point=web_search)
        search = search_flow.invoke(
            objective="What is the Railtracks agent framework?",
            search_queries=["railtracks python agent framework"],
            session_id=session_id,
        )
        results = json.loads(result_text(search))["results"]
        for hit in results:
            print(f"{hit['title']}\n{hit['url']}\n")

        fetch_flow = rt.Flow("parallel-web-fetch", entry_point=web_fetch)
        page = fetch_flow.invoke(
            urls=[results[0]["url"]],
            objective="What is Railtracks?",
            session_id=session_id,
        )
        print(result_text(page)[:2000])


if __name__ == "__main__":
    main()
# --8<-- [end: parallel_search_mcp]
