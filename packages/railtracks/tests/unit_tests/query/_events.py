"""Reusable event dicts for the query test modules.

Fixtures use the real event shapes from ``railtracks.events`` — flat payloads with
``spatial_parent_*`` / ``parent_*`` subfields as the write side emits them.
"""

from __future__ import annotations

LLM_RESPONSE = {
    "event_id": "evt_llm_1",
    "event_type": "llm.response",
    "scope_type": "session",
    "scope_id": "sess_a1",
    "parent_scope_id": None,
    "stamp": "2026-07-10T14:00:00.000+00:00",
    "payload": {
        "spatial_parent_type": "node",
        "spatial_parent_node_id": "node_root",
        "parent_type": "llm",
        "parent_llm_type_id": "llm_type_a",
        "parent_llm_invoke_id": "llm_invoke_b",
        "timestamp": "2026-07-10T14:00:00.000+00:00",
        "message_input": [{"role": "user", "content": "hi"}],
        "output": {"role": "assistant", "content": "hello"},
        "input_tokens": 812,
        "output_tokens": 204,
        "total_cost": 0.005,
        "latency": 1.2,
        "system_fingerprint": "fp_abc",
    },
}

LLM_CREATION = {
    "event_id": "evt_llm_0",
    "event_type": "llm.creation",
    "scope_type": "session",
    "scope_id": "sess_a1",
    "parent_scope_id": None,
    "stamp": "2026-07-10T13:59:59.000+00:00",
    "payload": {
        "spatial_parent_type": "none",
        "timestamp": "2026-07-10T13:59:59.000+00:00",
        "llm_id": "llm_type_a",
        "model_provider": "Anthropic",
        "model_name": "claude-opus-4-7",
    },
}

NODE_CREATION = {
    "event_id": "evt_node_1",
    "event_type": "node.creation",
    "scope_type": "session",
    "scope_id": "sess_a1",
    "parent_scope_id": None,
    "stamp": "2026-07-10T14:00:00.100+00:00",
    "payload": {
        "spatial_parent_type": "none",
        "timestamp": "2026-07-10T14:00:00.100+00:00",
        "node_id": "node_root",
        "name": "Root",
        "node_type": "Agent",
    },
}

SESSION_STARTED = {
    "event_id": "evt_session_1",
    "event_type": "session.started",
    "scope_type": "session",
    "scope_id": "sess_a1",
    "parent_scope_id": None,
    "stamp": "2026-07-10T13:59:58.000+00:00",
    "payload": {
        "spatial_parent_type": "none",
        "timestamp": "2026-07-10T13:59:58.000+00:00",
        "session_id": "sess_a1",
        "flow_name": "demo_flow",
        "flow_id": "flow_1",
        "session_name": "demo",
        "entry_point_name": "BasicStringAgent",
        "timeout": 60.0,
        "end_on_error": True,
        "save_state": False,
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
