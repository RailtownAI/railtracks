__all__ = [
    "agent_node",
    "middleware",
]


def __getattr__(name):
    if name == "agent_node":
        from .node import agent_node

        return agent_node
    if name == "middleware":
        from . import middleware

        return middleware
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
