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
        "spatial_parent_spatial_type": "node",
        "spatial_parent_node_id": "node_root",
        "parent_parent_type": "llm",
        "parent_llm_type_id": "llm_type_a",
        "parent_llm_invoke_id": "llm_invoke_b",
        "timestamp": "2026-07-10T14:00:00.000+00:00",
        "message_input": None,
        "output": None,
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
        "spatial_parent_spatial_type": "none",
        "timestamp": "2026-07-10T13:59:59.000+00:00",
        "llm_model_id": "llm_type_a",
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
        "spatial_parent_spatial_type": "none",
        "timestamp": "2026-07-10T14:00:00.100+00:00",
        "node_id": "node_root",
        "name": "Root",
        "node_type": "Agent",
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
