## Hosted Evaluations
**Conductr** can trigger your evaluations for you. Host an endpoint at `/evals/run`, and Conductr sends it the id of the agent run to evaluate:

```json
{"agent_run_id": "975b3a98-f7fa-4d61-89f3-bd4f243feb68"}
```

The endpoint pulls that run from Conductr, evaluates it, and uploads the results back. Here is a minimal version with FastAPI:

```python
--8<-- "docs/scripts/evaluations/conductr_hosted.py:endpoint"
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
- Swap in whichever [evaluators](evaluators/evaluators.md) you want to run.

The endpoint both retrieves runs and uploads evaluations, so it needs every key listed under [Evaluating Agent Runs](conductr.md).
