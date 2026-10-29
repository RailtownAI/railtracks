Numerical metrics are key in reporting evaluations that relate to system level results or any other mathematically quantifiable outcomes. In **Railtracks** we mainly use these metrics in the following evaluators:

- [`ToolUseEvaluator`](https://docs.railtracks.org/evaluations/evaluators/tool_use_evaluator/index.md): To report invocation count and failure rate for the tools of an agent.
- [`LLMInferenceEvaluator`](https://docs.railtracks.org/evaluations/evaluators/llm_inference_evaluator/index.md): To report LLM calls and their corresponding usage statistics for agent invocations.
- [`JudgeEvaluator`](https://docs.railtracks.org/evaluations/evaluators/judge_evaluator/index.md): To have an LLM grade agent outputs on a numerical scale.

## Usage

```python
from railtracks import evaluation as eval

latency = eval.metrics.Numerical(
    name="Latency",
    min_value=0.0,
    description="Response time in seconds.",  # optional
)
```

`Numerical` metrics also support optional `min_value` and `max_value` bounds, which are used by the visualizer to scale results correctly.

When used with the `JudgeEvaluator`, you can provide `shots` (also known as anchor points) to calibrate how the LLM assigns scores. Each shot maps a score to what it means, and the judge is told to interpolate between shots:

```python
from railtracks import evaluations as evals

quality = evals.metrics.Numerical(
    name="Quality",
    min_value=0,
    max_value=10,
    shots=[
        (0, "Completely incorrect and unhelpful."),
        (5, "Partially correct but missing key details."),
        (10, "Correct, complete, and well-structured."),
    ],
)
```

You do not need to provide a shot for every score; the judge interpolates between the provided anchor points.
