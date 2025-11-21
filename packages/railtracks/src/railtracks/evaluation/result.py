from datetime import datetime
from uuid import UUID
from pydantic import BaseModel
from .evaluators.metrics import Metric, Categorical, Continuous

class AgentRun(BaseModel):
    session_id: UUID
    run_id: UUID

class MetricResult(BaseModel):
    metric: Metric
    value: str | float | int

class EvaluatorResult(BaseModel):
    name: str
    evaluator_id: UUID
    config_hash: str
    results: list[MetricResult]
    agent_run_ids: list[AgentRun]
    
class EvaluationResult(BaseModel):    
    evaluation_id: UUID
    evaluation_name: str
    agent_name: str
    created_at: datetime
    agent_runs: list[str] # list of agent runs that were a part of this evaluation
    results: list[EvaluatorResult]
    metrics: list[Metric | Continuous | Categorical]

if __name__ == "__main__":
    from uuid import uuid4
    from datetime import datetime

    # Create sample agent runs
    session_id = uuid4()
    agent_run1 = AgentRun(session_id=session_id, run_id=uuid4())
    agent_run2 = AgentRun(session_id=session_id, run_id=uuid4())

    session_id = uuid4()
    agent_run3 = AgentRun(session_id=session_id, run_id=uuid4())
    agent_run4 = AgentRun(session_id=session_id, run_id=uuid4())

    # Create metrics
    metric1 = Continuous(name="Accuracy", min_value=0.0, max_value=1.0)
    metric_value1 = MetricValue(metric=metric1, value=0.95)

    metric2 = Categorical(name="Sentiment", categories=["Positive", "Negative", "Neutral"])
    metric_value2 = MetricValue(metric=metric2, value="Positive")

    # Create evaluator result
    evaluator_result = EvaluatorResult(
        name="SampleEvaluator",
        evaluator_id=uuid4(),
        config_hash="abc123def456",
        results=[metric_value1, metric_value2],
        agent_run_ids=[agent_run1, agent_run2]
    )
    evaluator_result2 = EvaluatorResult(
        name="AnotherEvaluator",
        evaluator_id=uuid4(),
        config_hash="def456ghi789",
        results=[metric_value1],
        agent_run_ids=[agent_run3, agent_run4]
    )

    # Create evaluation result
    evaluation_result = EvaluationResult(
        evaluation_id=uuid4(),
        evaluation_name="SampleEvaluation",
        agent_name="SampleAgent",
        created_at=datetime.now(),
        agent_runs=[agent_run1.run_id, agent_run2.run_id, agent_run3.run_id, agent_run4.run_id],
        results=[evaluator_result, evaluator_result2],
        metrics=[metric1, metric2]
    )

    import json
    
    with open("packages/railtracks/src/railtracks/evaluation/data.json", "w") as f:
        json.dump(evaluation_result.model_dump(mode="json"), f, indent=2)