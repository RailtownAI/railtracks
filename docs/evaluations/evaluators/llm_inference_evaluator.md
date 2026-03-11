The **`LLMInferenceEvaluator`** analyzes the LLM calls recorded in past agent runs and reports token usage, cost, and latency statistics. It requires no configuration, all metrics are derived from the session data automatically.

## Usage

```python
from railtracks import evaluation as eval

data = eval.extract_agent_data_points(".railtracks/data/sessions/")

evaluator = eval.LLMInferenceEvaluator()
results = eval.evaluate(data=data, evaluators=[evaluator])
```

## Metrics Tracked

The following metrics are collected **per LLM call**, broken down by model name, model provider, and call index:

| Metric | Description |
|---|---|
| `InputTokens` | Number of prompt tokens sent to the model. |
| `OutputTokens` | Number of tokens in the model's response. |
| `TokenCost` | Total cost of the call in USD. |
| `Latency` | Wall-clock time for the call in seconds. |

Aggregated (mean) values are calculated across runs for each `(model_name, model_provider, call_index)` group, making it straightforward to compare cost and speed across agent versions or model providers.