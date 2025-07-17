#   -------------------------------------------------------------
#   Copyright (c) Railtown AI. All rights reserved.
#   Licensed under the MIT License. See LICENSE in project root for information.
#   -------------------------------------------------------------
"""Railtown AI Request Completion Framework for building resilient agentic systems"""

from __future__ import annotations

from dotenv import load_dotenv

__all__ = [
    "Node",
    "library",
    "Runner",
    "call",
    "call_sync",
    "stream",
    "batch",
    "rc_mcp",
    "ExecutionInfo",
    "ExecutorConfig",
    "llm",
    "context",
    "set_config",
    "set_streamer",
    "context",
    "to_node",
]


from . import context, llm, rc_mcp
from .config import ExecutorConfig
from .context.central import set_config, set_streamer
from .interaction.batch import batch
from .interaction.call import call, call_sync
from .interaction.stream import stream
from .nodes import library
from .nodes.library.function import to_node
from .nodes.nodes import Node
from .run import ExecutionInfo, Runner

load_dotenv()
# Only change the MAJOR.MINOR if you need to. Do not change the PATCH. (vMAJOR.MINOR.PATCH).
__version__ = "0.1.0"
