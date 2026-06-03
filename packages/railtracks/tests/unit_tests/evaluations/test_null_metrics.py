import json
import uuid
import pytest
from pathlib import Path
from railtracks.evaluations.point import extract_agent_data_points, AgentDataPoint
from railtracks.evaluations.evaluators.llm_inference_evaluator import LLMInferenceEvaluator
from railtracks.evaluations.runners._evaluate import evaluate

@pytest.fixture
def session_with_null_metrics(tmp_path):
    """Create a temporary session file with null values for metrics."""
    session_id = str(uuid.uuid4())
    agent_node_id = str(uuid.uuid4())
    session_data = {
        "session_id": session_id,
        "runs": [
            {
                "nodes": [
                    {
                        "identifier": agent_node_id,
                        "node_type": "Agent",
                        "name": "Test Agent",
                        "details": {
                            "internals": {
                                "llm_details": [
                                    {
                                        "model_name": "gpt-4",
                                        "model_provider": "openai",
                                        "input": [{"role": "user", "content": "hello"}],
                                        "output": {"role": "assistant", "content": "hi"},
                                        "input_tokens": None,
                                        "output_tokens": 10,
                                        "total_cost": None,
                                        "latency": 0.5
                                    },
                                    {
                                        "model_name": "gpt-4",
                                        "model_provider": "openai",
                                        "input": [{"role": "user", "content": "world"}],
                                        "output": {"role": "assistant", "content": "hello"},
                                        "input_tokens": 5,
                                        "output_tokens": None,
                                        "total_cost": 0.01,
                                        "latency": None
                                    }
                                ]
                            }
                        }
                    }
                ],
                "edges": []
            }
        ]
    }
    
    session_file = tmp_path / f"{session_id}.json"
    session_file.write_text(json.dumps(session_data))
    return tmp_path

def test_extract_agent_data_points_with_null_metrics(session_with_null_metrics):
    """Ensure extract_agent_data_points handles null metrics without validation errors."""
    data_points = extract_agent_data_points(str(session_with_null_metrics))
    assert len(data_points) == 1
    adp = data_points[0]
    
    # Check that nulls are preserved correctly
    assert adp.llm_details.calls[0].input_tokens is None
    assert adp.llm_details.calls[0].total_cost is None
    assert adp.llm_details.calls[1].output_tokens is None
    assert adp.llm_details.calls[1].latency is None
    
    # Check that valid values are also preserved
    assert adp.llm_details.calls[0].output_tokens == 10
    assert adp.llm_details.calls[1].total_cost == 0.01

def test_llm_inference_evaluator_with_null_metrics(session_with_null_metrics):
    """Ensure LLMInferenceEvaluator skips null values in aggregation."""
    data_points = extract_agent_data_points(str(session_with_null_metrics))
    evaluator = LLMInferenceEvaluator()
    result = evaluator.run(data_points)
    
    # Verify cost aggregate skips the None value
    token_cost_aggregates = [
        node for node in result.aggregate_results.nodes.values() 
        if getattr(node, "name", "").startswith("Aggregate/TokenCost")
    ]
    
    # We expect one aggregate for Call_1 (Call_0 has total_cost=None and is skipped)
    assert len(token_cost_aggregates) == 1
    agg = token_cost_aggregates[0]
    assert agg.llm_call_index == 1
    assert agg.mean == 0.01
    assert agg.values == [0.01]

def test_evaluate_runner_with_null_metrics(session_with_null_metrics):
    """Ensure the full evaluate() flow works with null metrics."""
    data_points = extract_agent_data_points(str(session_with_null_metrics))
    evaluator = LLMInferenceEvaluator()
    
    # Should not raise any exceptions
    results = evaluate(
        data=data_points,
        evaluators=[evaluator],
        agent_selection=False
    )
    assert len(results) == 1
