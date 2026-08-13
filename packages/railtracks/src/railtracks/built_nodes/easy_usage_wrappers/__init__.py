from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .agent import agent_node
    from .function import function_node

__all__ = [
    "agent_node",
    "function_node",
]


def __dir__() -> list[str]:
    return __all__


def __getattr__(name: str):
    if name == "agent_node":
        from .agent import agent_node

        return agent_node
    if name == "function_node":
        from .function import function_node

        return function_node
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
