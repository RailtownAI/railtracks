Numerical metrics are key in reporting evaluations that relate to system level results or any other mathematically quantifiable outcomes. In **Railtracks** we mainly use these metrics in the following evaluators:

- [`ToolUseEvaluator`](../evaluators/tool_use_evaluator.md): To report invocation count and failure rate for the tools of an agent.
- [`LLMInferenceEvaluator`](../evaluators/llm_inference_evaluator.md): To report LLM calls and their corresponding usage statistics for agent invocations.

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