The **`ToolUseEvaluator`** assesses past agent runs and reports per-tool invocation counts, failure rates, and runtimes.

## Usage

```python
--8<-- "docs/scripts/evaluations/tool_use_evaluator.py"
```

## Metrics Tracked

| Metric | Description |
|---|---|
| `UsageCount` | Number of times each tool was called per agent run. |
| `FailureRate` | Fraction of calls that failed (0.0–1.0) per agent run. |
| `Runtime` | Wall-clock execution time per individual tool call (seconds). |