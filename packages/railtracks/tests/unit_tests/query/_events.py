"""Reusable event dicts for the query test modules."""

from __future__ import annotations

LLM_CALL = {
    "event_id": "evt_llm_1",
    "event_type": "llm.call",
    "scope_type": "session",
    "scope_id": "sess_a1",
    "parent_scope_id": None,
    "stamp": "2026-07-10T14:00:00.000+00:00",
    "payload": {
        "session_id": "sess_a1",
        "node_id": "node_root",
        "model": "claude-opus-4-7",
        "provider": "Anthropic",
        "input_tokens": 812,
        "output_tokens": 204,
        "total_cost": 0.005,
        "latency_s": 1.2,
    },
}

NODE_START = {
    "event_id": "evt_node_1",
    "event_type": "node.start",
    "scope_type": "session",
    "scope_id": "sess_a1",
    "parent_scope_id": None,
    "stamp": "2026-07-10T14:00:00.100+00:00",
    "payload": {
        "session_id": "sess_a1",
        "node_id": "node_root",
        "node_type": "Agent",
        "node_name": "Root",
    },
}

CUSTOM_NS_EVENT = {
    "event_id": "evt_custom_1",
    "event_type": "custom.thing",
    "scope_type": "session",
    "scope_id": "sess_a1",
    "parent_scope_id": None,
    "stamp": "2026-07-10T14:00:00.200+00:00",
    "payload": {"foo": "bar", "children": [{"x": 1}]},
}
