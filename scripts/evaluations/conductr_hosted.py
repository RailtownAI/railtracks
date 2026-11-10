# --8<-- [start: endpoint]
from typing import Any
from uuid import uuid4

import railtownai
from fastapi import FastAPI
from pydantic import BaseModel
from railtownai import HostedEvaluationResponse, upload_agent_evaluation
from railtracks import evaluations as evals

app = FastAPI()

evaluators = [evals.ToolUseEvaluator(), evals.LLMInferenceEvaluator()]


class EvaluationRequest(BaseModel):
    agent_run_id: str


@app.post("/evals/run", response_model=HostedEvaluationResponse)
def run_evaluation(request: EvaluationRequest) -> HostedEvaluationResponse:
    agent_run_id = request.agent_run_id
    evaluation_name = f"eval-{agent_run_id}-{uuid4().hex[:8]}"

    payload = railtownai.get_agent_runs([agent_run_id], skip_errors=True)
    data = evals.extract_agent_data_points(payload) if payload else []

    uploads: list[bool] = []

    def upload(evaluation: dict[str, Any]) -> None:
        uploads.append(upload_agent_evaluation(evaluation))

    if data:
        evals.evaluate(
            data=data,
            evaluators=evaluators,
            agent_selection=False,
            name=evaluation_name,
            payload_callback=upload,  # Your evals will be sent to Conductr automatically
        )

    return HostedEvaluationResponse(
        agent_run_id=agent_run_id,
        evaluation_name=evaluation_name,
        data_points=len(data),
        upload=bool(uploads) and all(uploads),
    )


# --8<-- [end: endpoint]
