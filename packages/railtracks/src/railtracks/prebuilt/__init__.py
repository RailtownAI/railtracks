######## Pre-built, ready-to-use add-ons: agents, middleware, guardrails, and tools. ########
#
# This package is a leaf in the dependency graph: it may import from anywhere in
# railtracks, but nothing outside `prebuilt/` may import from it. That one-way rule
# is what lets prebuilt add-ons freely reference built_nodes/llm/middleware/guardrails
# without creating import cycles (see design-docs/addon-interface, D6).

from railtracks.prebuilt import guardrails, middleware
from railtracks.prebuilt.rag_node import rag_node

# `tools` (memory, todo, ...) will be reimplemented here later; add it back to the
# imports and __all__ when it lands.
__all__ = ["rag_node", "middleware", "guardrails"]
