from pydantic import BaseModel, Field, field_serializer
from typing import Any
from uuid import UUID, uuid4

class AgentDataPoint(BaseModel):
    """A data point specific to agent interactions."""
    run_id: UUID
    agent_name: str
    agent_input: dict[str, Any]
    agent_output: Any = None
    agent_internals: dict[str, Any]

    @field_serializer('agent_output', when_used='json')
    def serialize_output(self, value: Any) -> Any:
        """Serialize BaseModel instances to dicts for JSON."""
        if isinstance(value, BaseModel):
            return value.model_dump(mode='json')
        return value


def extract_llm_metrics(llm_details_list):
    """
    Extract LLM metrics from llm_details list and compute aggregates.
    
    Args:
        llm_details_list: List of LLM detail dictionaries containing tokens, cost, and latency info.
    
    Returns:
        dict: Dictionary with 'aggregate' and 'calls' keys, or None if no LLM details.
              - aggregate: Contains total tokens, cost, latency across all calls
              - calls: List of individual call metrics with call_index
    """
    if not llm_details_list:
        return None
    
    calls = []
    total_input_tokens = 0
    total_output_tokens = 0
    total_cost = 0.0
    total_latency = 0.0
    has_tokens = False
    has_cost = False
    has_latency = False
    
    for idx, detail in enumerate(llm_details_list):
        call_data = {
            "call_index": idx,
            "model_name": detail.get("model_name"),
            "model_provider": detail.get("model_provider"),
            "input_tokens": detail.get("input_tokens"),
            "output_tokens": detail.get("output_tokens"),
            "total_cost": detail.get("total_cost"),
            "latency": detail.get("latency"),
            "system_fingerprint": detail.get("system_fingerprint"),
        }
        calls.append(call_data)
        
        # Aggregate metrics if available
        if detail.get("input_tokens") is not None:
            total_input_tokens += detail["input_tokens"]
            has_tokens = True
        if detail.get("output_tokens") is not None:
            total_output_tokens += detail["output_tokens"]
            has_tokens = True
        if detail.get("total_cost") is not None:
            total_cost += detail["total_cost"]
            has_cost = True
        if detail.get("latency") is not None:
            total_latency += detail["latency"]
            has_latency = True
    
    aggregate = {
        "total_input_tokens": total_input_tokens if has_tokens else None,
        "total_output_tokens": total_output_tokens if has_tokens else None,
        "total_tokens": (total_input_tokens + total_output_tokens) if has_tokens else None,
        "total_cost": total_cost if has_cost else None,
        "total_latency": total_latency if has_latency else None,
        "num_llm_calls": len(llm_details_list),
    }
    
    return {
        "aggregate": aggregate,
        "calls": calls,
    }