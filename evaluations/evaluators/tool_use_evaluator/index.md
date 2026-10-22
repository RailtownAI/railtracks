The **`ToolUseEvaluator`** assesses past agent runs and reports per-tool invocation counts, failure rates, and runtimes.

## Usage

```python
from railtracks import evaluations as evals

data = evals.extract_agent_data_points(".railtracks/data/sessions/")

evaluator = evals.ToolUseEvaluator()
results = evals.evaluate(data=data, evaluators=[evaluator])
```

## Metrics Tracked

| Metric        | Description                                                   |
| ------------- | ------------------------------------------------------------- |
| `UsageCount`  | Number of times each tool was called per agent run.           |
| `FailureRate` | Fraction of calls that failed (0.0–1.0) per agent run.        |
| `Runtime`     | Wall-clock execution time per individual tool call (seconds). |
