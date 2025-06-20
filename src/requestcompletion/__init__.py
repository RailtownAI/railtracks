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
    "mcp",
    "ExecutionInfo",
    "ExecutorConfig",
    "llm",
    "context",
    "set_config",
    "set_streamer",
    "context",
    "to_node",
]


from . import mcp
from .nodes import library
from .nodes.nodes import Node
from .interaction.call import call, call_sync
from .interaction.stream import stream
from .interaction.batch import batch
from .run import Runner, ExecutionInfo
from .context.central import set_config, set_streamer
from .config import ExecutorConfig
from . import llm
from . import context
from .nodes.library.function import to_node

load_dotenv()
# Only change the MAJOR.MINOR if you need to. Do not change the PATCH. (vMAJOR.MINOR.PATCH).
__version__ = "0.1.0"
