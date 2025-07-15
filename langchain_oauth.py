from dotenv import load_dotenv
import requests
from requests.auth import HTTPBasicAuth
import os
load_dotenv()

# tools = from_mcp_server(MCPHttpParams(url="https://remote.mcpservers.org/fetch/mcp"))     
# tools = from_mcp_server(MCPHttpParams(url="https://mcp.paypal.com/sse"))


def get_paypal_auth():
    response = requests.post(   # paypal only atm
        "https://api-m.sandbox.paypal.com/v1/oauth2/token",
        headers={"Accept": "application/json", "Accept-Language": "en_US"},
        data={"grant_type": "client_credentials"},
        auth=HTTPBasicAuth(
            os.getenv("PAYPAL_CLIENT_ID"), os.getenv("PAYPAL_CLIENT_SECRET")
        ),
    )
    response.raise_for_status()
    access_token = response.json()["access_token"]

    return access_token

paypal_headers = {"Authorization": f"Bearer {get_paypal_auth()}"}

# #paragon 
# import requestcompletion as rc
# paypal_headers = {"Authorization": f"Bearer {rc.oauth("paypal")}"}

def request_completion():
    import requestcompletion as rc
    from requestcompletion.nodes.library import from_mcp_server, tool_call_llm
    from requestcompletion.rc_mcp import MCPHttpParams

    fetch_tools = from_mcp_server(MCPHttpParams(url="https://remote.mcpservers.org/fetch/mcp")).tools
    paypal_tools = from_mcp_server(MCPHttpParams(url="https://mcp.paypal.com/sse", headers=paypal_headers)).tools
    tools = fetch_tools + paypal_tools
    agent = tool_call_llm(
        connected_nodes={*tools},
        system_message="""You are a master paypal agent. You love creating beautiful
     and well-structured paypal pages and make sure that everything is correctly formatted.""",
        model=rc.llm.OpenAILLM("gpt-4o"),
    ) 

    user_prompt = """List the tools you available to you related to paypal"""
    mh = rc.llm.MessageHistory([rc.llm.UserMessage(user_prompt)])

    with rc.Runner(rc.ExecutorConfig(logging_setting="VERBOSE")) as run:
        result = run.run_sync(agent, mh)
        print(result.answer.content)

# Run the functions
# asyncio.run(request_completion())
request_completion()