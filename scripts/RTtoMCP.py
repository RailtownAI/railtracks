from operator import add
import railtracks as rt

# --8<-- [start: simple_mcp_creation]
import railtracks as rt

# Start by creating your tools
@rt.function_node
def add_nums_plus_ten(num1: int, num2: int):
    """Simple tool example."""
    return num1 + num2 + 10

# Create your MCP server with the function node
mcp = rt.create_mcp_server([add_nums_plus_ten], server_name="My MCP Server")

# Now run the MCP server
mcp.run(transport="streamable-http", host="127.0.0.1", port=8000)
# --8<-- [end: simple_mcp_creation]

# --8<-- [start: accessing_mcp]
server = rt.connect_mcp(rt.MCPHttpParams(url="http://127.0.0.1:8000/mcp"))
tools = server.tools
# --8<-- [end: accessing_mcp]