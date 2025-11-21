#   -------------------------------------------------------------
#   Copyright (c) Railtown AI. All rights reserved.
#   Licensed under the MIT License. See LICENSE in project root for information.
#   -------------------------------------------------------------
"""The Railtracks Framework for building resilient agentic systems in simple python"""

from __future__ import annotations

from dotenv import load_dotenv

__all__ = [
    "Session",
    "session",
    "call",
    "broadcast",
    "call_batch",
    "interactive",
    "ExecutionInfo",
    "ExecutorConfig",
    "llm",
    "context",
    "set_config",
    "context",
    "function_node",
    "agent_node",
    "integrations",
    "prebuilt",
    "MCPStdioParams",
    "MCPHttpParams",
    "connect_mcp",
    "create_mcp_server",
    "ToolManifest",
    "session_id",
    "vector_stores",
    "rag",
    "RagConfig",
]


from railtracks.built_nodes.concrete.rag import RagConfig
from railtracks.built_nodes.easy_usage_wrappers import (
    agent_node,
    function_node,
)

from . import context, integrations, llm, prebuilt, rag, vector_stores
from ._session import ExecutionInfo, Session, session
from .context.central import session_id, set_config
from .interaction import broadcast, call, call_batch, interactive
from .nodes.manifest import ToolManifest
from .rt_mcp import MCPHttpParams, MCPStdioParams, connect_mcp, create_mcp_server
from .utils.config import ExecutorConfig
from .utils.logging.config import initialize_module_logging

load_dotenv()
initialize_module_logging()

# Do not worry about changing this version number manually. It will updated on release.
__version__ = "1.0.0"
