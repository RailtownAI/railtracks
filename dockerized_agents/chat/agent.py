import requestcompletion as rc
from typing import Dict, Any
import os, aiohttp
from requestcompletion.rc_mcp import MCPHttpParams
from requestcompletion.nodes.library import from_mcp_server, chat_tool_call_llm


# ============================== MCP Tools that can seach URLs ==============================
fetch_mcp_server = from_mcp_server(MCPHttpParams(url="https://remote.mcpservers.org/fetch/mcp"))
fetch_mcp_tools = fetch_mcp_server.tools
# ===========================================================================================

# ============================== Cutoms Search Tool using Google API ==============================
# Helper 
def _format_results(data: Dict[str, Any]) -> Dict[str, Any]:
    """Format Google API response"""
    results = []
    
    if 'items' in data:
        for item in data['items']:
            result = {
                'title': item.get('title', ''),
                'snippet': item.get('snippet', ''),
                'url': item.get('link', ''),
                'siteName': item.get('displayLink', ''),
                'byline': ''  # Google API doesn't provide author info
            }
            results.append(result)
    
    return {
        'query': data.get('queries', {}).get('request', [{}])[0].get('searchTerms', ''),
        'results': results,
        'totalResults': data.get('searchInformation', {}).get('totalResults', '0')
    }
    
@rc.to_node
async def google_search(query: str, num_results: int = 3) -> Dict[str, Any]:
    """
    Tool for searching using Google Custom Search API
    NOTE: Requires API key and search engine ID from Google Cloud Console
    Args:
        query (str): The search query
        num_results (int): The number of results to return
    Returns:
        Dict[str, Any]: The search results
    """
    params = {
        'key': os.environ['GOOGLE_SEARCH_API_KEY'],
        'cx': os.environ['GOOGLE_SEARCH_ENGINE_ID'],
        'q': query,
        'num': min(num_results, 5)  # Google API max is 5
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get("https://www.googleapis.com/customsearch/v1", params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return _format_results(data)
                else:
                    error_text = await response.text()
                    raise Exception(f"Google API error {response.status}: {error_text}")
        except Exception as e:
            raise Exception(f"Search failed: {str(e)}")


# ================== Construct the Agent =================
tools = fetch_mcp_tools + [google_search]
ChatBot = chat_tool_call_llm(
    model=rc.llm.OpenAILLM("gpt-4o"),
    pretty_name="ChatBot",
    system_message=rc.llm.SystemMessage(
        "You are an agent capable of answering user questions. You have tool access as well with a maximum of 10 calls. You can let the user know if you ran out of tool calls."
    ),
    output_type="MessageHistory",
    connected_nodes={*tools},
    max_tool_calls=10,
)

with rc.Runner(rc.ExecutorConfig(timeout=600)) as runner:
    resp = runner.run_sync(
        ChatBot,
        rc.llm.MessageHistory(),
    )