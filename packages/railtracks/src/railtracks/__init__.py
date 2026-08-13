#   -------------------------------------------------------------
#   Copyright (c) Railtown AI. All rights reserved.
#   Licensed under the MIT License. See LICENSE in project root for information.
#   -------------------------------------------------------------
"""The Railtracks Framework for building resilient agentic systems in simple python"""

from __future__ import annotations

import importlib
import logging
from typing import TYPE_CHECKING

from dotenv import load_dotenv

if TYPE_CHECKING:
    from railtracks import retrieval
    from railtracks.interaction import interactive as interactive

__all__ = [
    "Session",
    "session",
    "call",
    "broadcast",
    "call_batch",
    "ExecutionInfo",
    "ExecutorConfig",
    "llm",
    "guardrails",
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
    "evaluations",
    "observability",
    "retrieval",
    "Flow",
    "enable_logging",
]

from railtracks.built_nodes import (
    agent_node,
    function_node,
)

from . import (
    context,
    evaluations,
    guardrails,
    integrations,
    llm,
    observability,
    prebuilt,
)
from ._session import ExecutionInfo, Session, session
from .context.central import session_id, set_config
from .interaction import broadcast, call, call_batch
from .nodes.manifest import ToolManifest
from .orchestration.flow import Flow
from .rt_mcp import MCPHttpParams, MCPStdioParams, connect_mcp, create_mcp_server
from .utils.config import ExecutorConfig
from .utils.deprecation import warn_pending_change
from .utils.logging.config import enable_logging

load_dotenv()

# Library does not configure logging by default. Add NullHandler so the RT logger
# never emits "No handlers could be found". Call enable_logging() to opt in.
logging.getLogger("RT").addHandler(logging.NullHandler())

# Do not worry about changing this version number manually. It will updated on release.
__version__ = "1.0.0"


def __getattr__(name: str):
    if name == "interactive":
        # Not cached in globals()
        warn_pending_change(
            "rt.interactive",
            change="is removed",
            detail="There is no replacement; the local chat UI is going away.",
        )
        return importlib.import_module("railtracks.interaction.interactive")
    if name == "retrieval":
        try:
            module = importlib.import_module("railtracks.retrieval")
        except ImportError as exc:
            raise ImportError(
                "railtracks.retrieval requires the retrieval extras. "
                "Install with: pip install 'railtracks[retrieval]'"
            ) from exc
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    # "interactive" is not in __all__ but is still reachable
    return sorted({*__all__, "interactive"})
