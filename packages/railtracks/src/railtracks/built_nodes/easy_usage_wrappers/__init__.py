from __future__ import annotations

from typing import TYPE_CHECKING

from railtracks.utils.deprecation import warn_pending_change

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
    if name in __all__:
        # This notice only fires for user imports of the package itself.
        warn_pending_change(
            f"Importing {name!r} from railtracks.built_nodes.easy_usage_wrappers",
            change="stops working",
            instead=f"railtracks.built_nodes.{name} (or rt.{name})",
            detail="This package is removed in 1.5.0.",
        )

    if name == "agent_node":
        from .agent import agent_node

        return agent_node
    if name == "function_node":
        from .function import function_node

        return function_node
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
