"""Node builders: Forward path

``agent_node`` and ``function_node`` are exported from here. They previously lived in
``railtracks.built_nodes.easy_usage_wrappers``, which is removed in railtracks 1.5.0.
"""

__all__ = [
    "agent_node",
    "function_node",
]


from .easy_usage_wrappers.agent import agent_node
from .easy_usage_wrappers.function import function_node
