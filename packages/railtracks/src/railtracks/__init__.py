#   -------------------------------------------------------------
#   Copyright (c) Railtown AI. All rights reserved.
#   Licensed under the MIT License. See LICENSE in project root for information.
#   -------------------------------------------------------------
"""Railtown AI RailTracks Framework for building resilient agentic systems"""

from __future__ import annotations

from dotenv import load_dotenv

__all__ = [
    "Node",
    "library",
    "Session",
    "call",
    "call_sync",
    "broadcast",
    "call_batch",
    "rt_mcp",
    "ExecutionInfo",
    "ExecutorConfig",
    "llm",
    "context",
    "set_config",
    "context",
    "function_node",
]


from railtracks.nodes.library.easy_usage_wrappers.function import function_node

from . import context, llm, rt_mcp
from .config import ExecutorConfig
from .context.central import set_config
from .interaction.batch import call_batch
from .interaction.call import call, call_sync
from .interaction.stream import broadcast
from .nodes import library
from .nodes.nodes import Node
from .run import ExecutionInfo, Session

load_dotenv()
# Only change the MAJOR.MINOR if you need to. Do not change the PATCH. (vMAJOR.MINOR.PATCH).
__version__ = "0.1.0"
