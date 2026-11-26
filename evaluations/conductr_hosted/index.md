## Hosted Evaluations

**Conductr** can trigger your evaluations for you. Host an endpoint at `/evals/run`, and Conductr sends it the id of the agent run to evaluate:

```json
{"agent_run_id": "975b3a98-f7fa-4d61-89f3-bd4f243feb68"}
```

The endpoint pulls that run from Conductr, evaluates it, and uploads the results back. Here is a minimal version with FastAPI:

```python
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
```

It responds with a `HostedEvaluationResponse`, from `railtownai` 2.1.2 or newer:

```json
{
    "agent_run_id": "975b3a98-f7fa-4d61-89f3-bd4f243feb68",
    "evaluation_name": "eval-975b3a98-f7fa-4d61-89f3-bd4f243feb68-5b25340b",
    "data_points": 1,
    "upload": true
}
```

Conductr doesn't require a response body yet, but keep returning `evaluation_name`: it's how Conductr will link back to the evaluation. `upload` is only `true` when every result reached Conductr, and `data_points` is `0` when the run couldn't be found.

A few things to keep in mind:

- Pass `agent_selection=False` to `evaluate`. Otherwise it prompts on the terminal when a run contains more than one agent, and the request hangs.
- The route is a plain `def` rather than `async def` because `get_agent_runs` and `evaluate` block. FastAPI runs a plain `def` in a worker thread instead of on the event loop.
- Swap in whichever [evaluators](https://docs.railtracks.org/evaluations/evaluators/evaluators/index.md) you want to run.

The endpoint both retrieves runs and uploads evaluations, so it needs every key listed under [Evaluating Agent Runs](https://docs.railtracks.org/evaluations/conductr/index.md).
