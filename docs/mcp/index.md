# MCP (Model Context Protocol) Integration

RC provides comprehensive support for MCP servers through both stdio and HTTP transports.

## Environment Compatibility

### Stdio MCP Servers

Stdio-based MCP servers require subprocess creation capabilities. They work well in:

- **✅ Standard Python environments** (command line, scripts, desktop applications)
- **✅ Most server environments** with subprocess support
- **✅ Local development environments**

However, stdio MCP servers may not work in restricted environments:

- **❌ Jupyter Notebooks** (subprocess restrictions)
- **❌ Streamlit applications** (subprocess restrictions)  
- **❌ Some cloud platforms** with security restrictions
- **❌ Containerized environments** with limited subprocess access

### HTTP MCP Servers

HTTP-based MCP servers work in all environments and are the recommended choice for:

- **✅ Jupyter Notebooks**
- **✅ Streamlit applications**
- **✅ Web applications**
- **✅ Restricted cloud environments**
- **✅ Any environment with HTTP access**

## Error Handling

When stdio MCP servers cannot be used due to environment restrictions, RC will raise a `StdioNotAvailableError` with clear guidance:

```python
from mcp import StdioServerParameters
from requestcompletion.rc_mcp.main import MCPAsyncClient, StdioNotAvailableError

config = StdioServerParameters(command="some-mcp-server", args=[])
client = MCPAsyncClient(config)

try:
    async with client:
        # Use the client
        pass
except StdioNotAvailableError as e:
    print(f"Stdio not available: {e}")
    # Consider using HTTP-based MCP server instead
```

## Recommended Patterns

### Graceful Fallback

```python
from mcp import StdioServerParameters
from requestcompletion.rc_mcp.main import MCPHttpParams, StdioNotAvailableError
from requestcompletion.nodes.library.mcp_tool import async_from_mcp_server

async def get_mcp_tools():
    # Try stdio first
    try:
        stdio_config = StdioServerParameters(
            command="my-mcp-server", 
            args=["--local"]
        )
        return await async_from_mcp_server(stdio_config)
    except StdioNotAvailableError:
        # Fallback to HTTP
        http_config = MCPHttpParams(url="https://my-server.com/mcp/sse")
        return await async_from_mcp_server(http_config)
```

### Environment-Specific Configuration

```python
import os
from mcp import StdioServerParameters
from requestcompletion.rc_mcp.main import MCPHttpParams

def get_mcp_config():
    if os.getenv("JUPYTER_SERVER_ROOT") or os.getenv("STREAMLIT_SERVER_PORT"):
        # We're likely in a restricted environment
        return MCPHttpParams(url="https://my-server.com/mcp/sse")
    else:
        # Standard environment, use stdio
        return StdioServerParameters(command="my-mcp-server", args=[])
```

## Best Practices

1. **Use HTTP for web applications** - HTTP MCP servers are more reliable in web environments
2. **Implement fallback logic** - Always have a backup plan when stdio fails
3. **Test in target environment** - Verify MCP connectivity in your deployment environment
4. **Handle errors gracefully** - Use `StdioNotAvailableError` to provide helpful user guidance