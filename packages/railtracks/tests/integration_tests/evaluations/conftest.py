"""Shared fixtures for evaluations integration tests."""

from unittest.mock import patch

import pytest


# ── Constants ─────────────────────────────────────────────────────────────────

AGENT_ID_1 = "aaaaaaaa-0000-0000-0000-000000000001"
AGENT_ID_2 = "aaaaaaaa-0000-0000-0000-000000000002"
TOOL_ID_1 = "bbbbbbbb-0000-0000-0000-000000000001"
TOOL_ID_2 = "bbbbbbbb-0000-0000-0000-000000000002"
SESSION_ID_1 = "cccccccc-0000-0000-0000-000000000001"
SESSION_ID_2 = "cccccccc-0000-0000-0000-000000000002"


# ── Session builder ───────────────────────────────────────────────────────────


def make_session_dict(
    *,
    agent_id: str,
    tool_id: str,
    session_id: str,
    agent_name: str = "StockAgent",
    input_tokens: int = 50,
    output_tokens: int = 10,
    total_cost: float = 0.001,
    llm_latency: float = 1.2,
    tool_runtime: float = 0.1,
    tool_status: str = "Completed",
) -> dict:
    """Build a minimal but realistic session dictionary."""
    return {
        "flow_name": "Stock Analysis",
        "flow_id": "flow01",
        "session_id": session_id,
        "session_name": None,
        "start_time": 1_000_000.0,
        "end_time": 1_000_016.0,
        "runs": [
            {
                "name": agent_name,
                "run_id": "run001",
                "status": "Completed",
                "nodes": [
                    {
                        "identifier": agent_id,
                        "node_type": "Agent",
                        "name": agent_name,
                        "details": {
                            "internals": {
                                "llm_details": [
                                    {
                                        "model_name": "gpt-4",
                                        "model_provider": "OpenAI",
                                        "input": [
                                            {"role": "system", "content": "You are helpful."},
                                            {"role": "user", "content": "Stock price?"},
                                        ],
                                        "output": {
                                            "role": "assistant",
                                            "content": "The stock is $100.",
                                        },
                                        "input_tokens": input_tokens,
                                        "output_tokens": output_tokens,
                                        "total_cost": total_cost,
                                        "latency": llm_latency,
                                    }
                                ]
                            }
                        },
                    },
                    {
                        "identifier": tool_id,
                        "node_type": "Tool",
                        "name": "get_stock_price",
                        "details": {
                            "internals": {"latency": {"total_time": tool_runtime}}
                        },
                    },
                ],
                "edges": [
                    {
                        "source": agent_id,
                        "target": tool_id,
                        "identifier": "dddddddd-0000-0000-0000-000000000001",
                        "details": {
                            "input_args": [],
                            "input_kwargs": {"ticker": "AMZN"},
                            "status": tool_status,
                            "output": 214.88,
                        },
                    },
                    {
                        "source": None,
                        "target": agent_id,
                        "identifier": "dddddddd-0000-0000-0000-000000000003",
                        "details": {
                            "input_args": ["What is the stock price?"],
                            "input_kwargs": {},
                            "status": "Completed",
                            "output": {"answer": "The stock is $100."},
                        },
                    },
                ],
            }
        ],
    }


# ── Payload fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def session_payload() -> dict:
    """A single session payload (one agent run)."""
    return make_session_dict(
        agent_id=AGENT_ID_1,
        tool_id=TOOL_ID_1,
        session_id=SESSION_ID_1,
    )


@pytest.fixture
def two_session_payloads() -> list[dict]:
    """Two session payloads representing two runs of the same agent."""
    return [
        make_session_dict(
            agent_id=AGENT_ID_1,
            tool_id=TOOL_ID_1,
            session_id=SESSION_ID_1,
        ),
        make_session_dict(
            agent_id=AGENT_ID_2,
            tool_id=TOOL_ID_2,
            session_id=SESSION_ID_2,
        ),
    ]


@pytest.fixture(autouse=True)
def no_save():
    """Prevent evaluate() from writing EvaluationResult JSON to disk in every test."""
    with patch("railtracks.evaluations.runners._evaluate.save"):
        yield
