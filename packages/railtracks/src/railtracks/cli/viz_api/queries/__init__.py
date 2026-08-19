"""DuckDB queries backing the visualizer API.

Callers do ``from ..viz_api import queries`` and reach every function through
this package (``queries.list_session_rows(...)``, ``queries.get_query(...)``).
The implementation is split by resource — sessions, nodes, LLM traces, events,
middleware, guardrails — with shared plumbing in ``_common`` and the DuckDB
connection lifecycle in ``_connection``.
"""

from ._connection import close_query, get_query
from .events import (
    count_event_rows,
    get_event_stats,
    list_event_filter_options,
    list_event_rows,
)
from .guardrails import list_guardrails_by_node
from .llm_traces import (
    count_llm_trace_rows,
    get_llm_trace_stats,
    list_llm_trace_filter_options,
    list_llm_trace_rows,
)
from .middleware import (
    count_middleware_rows,
    get_middleware_stats,
    list_middleware_by_session,
    list_middleware_filter_options,
    list_middleware_rows,
)
from .nodes import (
    get_agent_llm_details,
    get_node_row,
    get_tool_io,
    list_llm_totals_by_node,
    list_session_node_rows,
)
from .sessions import (
    get_session_row,
    get_session_stats,
    list_session_filter_options,
    list_session_rows,
)

__all__ = [
    "close_query",
    "count_event_rows",
    "count_llm_trace_rows",
    "count_middleware_rows",
    "get_agent_llm_details",
    "get_event_stats",
    "get_llm_trace_stats",
    "get_middleware_stats",
    "get_node_row",
    "get_query",
    "get_session_row",
    "get_session_stats",
    "get_tool_io",
    "list_event_filter_options",
    "list_event_rows",
    "list_guardrails_by_node",
    "list_llm_totals_by_node",
    "list_llm_trace_filter_options",
    "list_llm_trace_rows",
    "list_middleware_by_session",
    "list_middleware_filter_options",
    "list_middleware_rows",
    "list_session_filter_options",
    "list_session_node_rows",
    "list_session_rows",
]
