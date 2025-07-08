import webbrowser
from contextlib import AsyncExitStack
from datetime import timedelta
from typing import Any, Dict

import httpx
from typing_extensions import Self

from mcp import ClientSession, StdioServerParameters
from mcp.client.auth import OAuthClientProvider
from mcp.shared.auth import OAuthClientMetadata
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.client.sse import sse_client

from pydantic import BaseModel
from ..llm import Tool
from ..rc_mcp.oauth import InMemoryTokenStorage, CallbackServer
from ..nodes.nodes import Node


class MCPHttpParams(BaseModel):
    url: str
    headers: dict[str, Any] | None = None
    timeout: timedelta = timedelta(seconds=30)
    sse_read_timeout: timedelta = timedelta(seconds=60 * 5)
    terminate_on_close: bool = True


class MCPAsyncClient:
    """
    Async client for communicating with an MCP server via stdio or HTTP Stream, with streaming support.

    If a client session is provided, it will be used; otherwise, a new session will be created.
    """

    def __init__(
        self,
        config: StdioServerParameters | MCPHttpParams,
        client_session: ClientSession | None = None,
    ):
        self.config = config
        self.session = client_session
        self.exit_stack = AsyncExitStack()
        self._tools_cache = None

    async def __aenter__(self):
        if isinstance(self.config, StdioServerParameters):
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(self.config)
            )
            self.session = await self.exit_stack.enter_async_context(
                ClientSession(*stdio_transport)
            )
            await self.session.initialize()
        elif isinstance(self.config, MCPHttpParams):
            await self._init_http()

        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.exit_stack.aclose()

    async def list_tools(self):
        if self._tools_cache is not None:
            return self._tools_cache
        else:
            resp = await self.session.list_tools()
            self._tools_cache = resp.tools
        return self._tools_cache

    async def call_tool(self, tool_name: str, tool_args: dict):
        return await self.session.call_tool(tool_name, tool_args)

    async def _init_http(self):
        # Set transport type based on URL ending
        if self.config.url.rstrip("/").endswith("/sse"):
            self.transport_type = "sse"
        else:
            self.transport_type = "streamable_http"

        async def get_oauth_metadata(server_url: str):
            from urllib.parse import urlparse, urlunparse, urljoin

            parsed = urlparse(server_url)
            base_url = urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))
            metadata_url = urljoin(base_url, "/.well-known/oauth-authorization-server")
            async with httpx.AsyncClient() as client:
                resp = await client.get(metadata_url)
                if resp.status_code == 200:
                    return resp.json()
                return None

        oauth_metadata = await get_oauth_metadata(self.config.url)

        if oauth_metadata:
            callback_server = CallbackServer(port=3000)
            callback_server.start()

            async def callback_handler() -> tuple[str, str | None]:
                print("⏳ Waiting for authorization callback...")
                try:
                    auth_code = callback_server.wait_for_callback(timeout=300)
                    return auth_code, callback_server.get_state()
                finally:
                    callback_server.stop()

            client_metadata_dict = {
                "client_name": "Simple Auth Client",
                "redirect_uris": ["http://localhost:3000/callback"],
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
                "token_endpoint_auth_method": "client_secret_post",
            }

            async def _default_redirect_handler(authorization_url: str) -> None:
                print(f"Opening browser for authorization: {authorization_url}")
                webbrowser.open(authorization_url)

            oauth_auth = OAuthClientProvider(
                server_url=self.config.url,
                client_metadata=OAuthClientMetadata.model_validate(
                    client_metadata_dict
                ),
                storage=InMemoryTokenStorage(),
                redirect_handler=_default_redirect_handler,
                callback_handler=callback_handler,
            )

            if self.transport_type == "sse":
                client = sse_client(
                    url=self.config.url,
                    headers=self.config.headers,
                    timeout=self.config.timeout.total_seconds(),
                    sse_read_timeout=self.config.sse_read_timeout.total_seconds(),
                    auth=oauth_auth,
                )
            else:
                client = streamablehttp_client(
                    url=self.config.url,
                    headers=self.config.headers,
                    timeout=self.config.timeout.total_seconds(),
                    sse_read_timeout=self.config.sse_read_timeout.total_seconds(),
                    terminate_on_close=self.config.terminate_on_close,
                    auth=oauth_auth,
                )
        else:
            if self.transport_type == "sse":
                client = sse_client(
                    url=self.config.url,
                    headers=self.config.headers,
                    timeout=self.config.timeout.total_seconds(),
                    sse_read_timeout=self.config.sse_read_timeout.total_seconds(),
                    auth=self.config.auth if hasattr(self.config, "auth") else None,
                )
            else:
                client = streamablehttp_client(
                    url=self.config.url,
                    headers=self.config.headers,
                    timeout=self.config.timeout,
                    sse_read_timeout=self.config.sse_read_timeout,
                    terminate_on_close=self.config.terminate_on_close,
                    auth=self.config.auth if hasattr(self.config, "auth") else None,
                )

        read_stream, write_stream, *_ = await self.exit_stack.enter_async_context(
            client
        )
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await self.session.initialize()


def from_mcp(
    tool,
    config: StdioServerParameters | MCPHttpParams,
):
    """
    Wrap an MCP tool as a Node class for use in the requestcompletion framework.

    Args:
        tool: The MCP tool object.
        config: Configuration parameters for the MCP client, either Stdio or HTTP.

    Returns:
        A Node subclass that invokes the MCP tool.
    """

    class MCPToolNode(Node):
        def __init__(self, **kwargs):
            super().__init__()
            self.kwargs = kwargs
            self.client = MCPAsyncClient(config)

        async def invoke(self):
            async with self.client:
                result = await self.client.call_tool(tool.name, self.kwargs)
            if hasattr(result, "content"):
                return result.content
            return result

        @classmethod
        def pretty_name(cls):
            return f"MCPToolNode({tool.name})"

        @classmethod
        def tool_info(cls) -> Tool:
            return Tool.from_mcp(tool)

        @classmethod
        def prepare_tool(cls, tool_parameters: Dict[str, Any]) -> Self:
            return cls(**tool_parameters)

    return MCPToolNode
