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
]


from .nodes.easy_usage_wrappers import function_node, agent_node, chatui_node

from . import context, llm, integrations
from .utils.config import ExecutorConfig
from .context.central import set_config
from .interaction import call, call_sync, call_batch, broadcast
from .session import ExecutionInfo, Session

load_dotenv()
# Only change the MAJOR.MINOR if you need to. Do not change the PATCH. (vMAJOR.MINOR.PATCH).
__version__ = "0.1.0"
