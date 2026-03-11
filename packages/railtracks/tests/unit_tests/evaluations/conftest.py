import json
from uuid import UUID

import pytest

from railtracks.evaluations.point import (
    EdgeDataPoint,
    NodeDataPoint,
    NodeType,
    extract_agent_data_points,
)

AGENT_ID = UUID("aaaaaaaa-0000-0000-0000-000000000001")
TOOL1_ID = UUID("bbbbbbbb-0000-0000-0000-000000000001")
TOOL2_ID = UUID("bbbbbbbb-0000-0000-0000-000000000002")
SESSION_ID = UUID("cccccccc-0000-0000-0000-000000000001")


@pytest.fixture
def agent_node():
    return NodeDataPoint(
        identifier=AGENT_ID,
        node_type=NodeType.AGENT,
        name="TestAgent",
        details={"internals": {"latency": {"total_time": 1.5}}},
    )


@pytest.fixture
def tool_nodes():
    return {
        TOOL1_ID: NodeDataPoint(
            identifier=TOOL1_ID,
            node_type=NodeType.TOOL,
            name="tool_one",
            details={"internals": {"latency": {"total_time": 0.1}}},
        ),
        TOOL2_ID: NodeDataPoint(
            identifier=TOOL2_ID,
            node_type=NodeType.TOOL,
            name="tool_two",
            details={"internals": {"latency": {"total_time": 0.2}}},
        ),
    }


@pytest.fixture
def edges():
    return {
        (AGENT_ID, TOOL1_ID): EdgeDataPoint(
            identifier=UUID("dddddddd-0000-0000-0000-000000000001"),
            source=AGENT_ID,
            target=TOOL1_ID,
            details={"input_args": [], "input_kwargs": {"ticker": "AMZN"}, "status": "Completed", "output": 214.88},
        ),
        (AGENT_ID, TOOL2_ID): EdgeDataPoint(
            identifier=UUID("dddddddd-0000-0000-0000-000000000002"),
            source=AGENT_ID,
            target=TOOL2_ID,
            details={"input_args": [], "input_kwargs": {}, "status": "Completed", "output": "2026-03-10"},
        ),
        (None, AGENT_ID): EdgeDataPoint(
            identifier=UUID("dddddddd-0000-0000-0000-000000000003"),
            source=None,
            target=AGENT_ID,
            details={
                "input_args": ["What is the stock price?"],
                "input_kwargs": {},
                "status": "Completed",
                "output": {"answer": "Here is the stock info"},
            },
        ),
    }


@pytest.fixture
def session_json():
    return {
        "flow_name": "Stock Analysis",
        "flow_id": "abc123",
        "session_id": str(SESSION_ID),
        "session_name": None,
        "start_time": 1000000.0,
        "end_time": 1000016.0,
        "runs": [
            {
                "name": "TestAgent",
                "run_id": "run001",
                "status": "Completed",
                "nodes": [
                    {
                        "identifier": str(AGENT_ID),
                        "node_type": "Agent",
                        "name": "TestAgent",
                        "details": {
                            "internals": {
                                "llm_details": [
                                    {
                                        "model_name": "gpt-4",
                                        "model_provider": "OpenAI",
                                        "input": [
                                            {"role": "system", "content": "You are an assistant."},
                                            {"role": "user", "content": "What is the stock price?"},
                                        ],
                                        "output": {"role": "assistant", "content": "The stock is $100."},
                                        "input_tokens": 50,
                                        "output_tokens": 10,
                                        "total_cost": 0.001,
                                        "latency": 1.2,
                                    }
                                ]
                            }
                        },
                    },
                    {
                        "identifier": str(TOOL1_ID),
                        "node_type": "Tool",
                        "name": "get_stock_price",
                        "details": {"internals": {"latency": {"total_time": 0.1}}},
                    },
                ],
                "edges": [
                    {
                        "source": str(AGENT_ID),
                        "target": str(TOOL1_ID),
                        "identifier": "dddddddd-0000-0000-0000-000000000001",
                        "details": {
                            "input_args": [],
                            "input_kwargs": {"ticker": "AMZN"},
                            "status": "Completed",
                            "output": 214.88,
                        },
                    },
                    {
                        "source": None,
                        "target": str(AGENT_ID),
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


@pytest.fixture
def agent_data_point(tmp_path, session_json):
    """A fully parsed AgentDataPoint, ready to use as input for evaluator tests."""
    path = tmp_path / "session.json"
    path.write_text(json.dumps(session_json))
    return extract_agent_data_points(str(path))[0]
