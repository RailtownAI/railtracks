##################################################################
# For this example, we are using an mcp provider that can fetch data from urls as well as a custom tool that uses Google API to search.
# 1. https://console.cloud.google.com/apis/api/customsearch.googleapis.com/
# 2. https://remote-mcp-servers.com/servers/ecc7629a-9f3a-487d-86fb-039f46016621
##################################################################
from dotenv import load_dotenv
import os
from requestcompletion.nodes.library import from_mcp_server, tool_call_llm
import requestcompletion as rc
from requestcompletion.rc_mcp import MCPHttpParams
import aiohttp
from typing import Dict, Any

load_dotenv()

# ============================== MCP Tools that can seach URLs ==============================
fetch_mcp_tools = from_mcp_server(MCPHttpParams(url="https://remote.mcpservers.org/fetch/mcp"))
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
    


##################################################################
# Example using the tools with an agent
tools = fetch_mcp_tools + [google_search]
agent = tool_call_llm(
    connected_nodes={*tools},
    system_message="""You are an infomation gathering agent that can search the web.""",
    model=rc.llm.OpenAILLM("gpt-4o"),
)

user_prompt = """Tell me about Railtown AI."""
message_history = rc.llm.MessageHistory()
message_history.append(rc.llm.UserMessage(user_prompt))


result = rc.call_sync(agent, message_history)

print(result)