#   -------------------------------------------------------------
#   Copyright (c) Railtown AI. All rights reserved.
#   Licensed under the MIT License. See LICENSE in project root for information.
#   -------------------------------------------------------------
"""Railtown AI RailTracks Framework for building resilient agentic systems"""

from __future__ import annotations

from dotenv import load_dotenv

__all__ = [
    "Session",
    "call",
    "call_sync",
    "broadcast",
    "call_batch",
    "ExecutionInfo",
    "ExecutorConfig",
    "llm",
    "context",
    "set_config",
    "context",
    "function_node",
    "agent_node",
    "chatui_node",
    "integrations",
    "prebuilt",
    "MCPStdioParams",
    "MCPHttpParams",
    "connect_mcp",
    "create_mcp_server",
]


from . import context, integrations, llm, prebuilt
from .context.central import set_config
from .interaction import broadcast, call, call_batch, call_sync
from .nodes.easy_usage_wrappers import agent_node, chatui_node, function_node
from .rt_mcp import MCPHttpParams, MCPStdioParams, connect_mcp, create_mcp_server
from .session import ExecutionInfo, Session
from .utils.config import ExecutorConfig

load_dotenv()
# Only change the MAJOR.MINOR if you need to. Do not change the PATCH. (vMAJOR.MINOR.PATCH).
__version__ = "1.0.0"
