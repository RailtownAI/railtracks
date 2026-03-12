The **`ToolUseEvaluator`** assesses past agent runs and reports per-tool invocation counts, failure rates, and runtimes.

!!! note
    Only `AgentDataPoint`s saved with full tracing enabled will include tool call data for this evaluator to analyze.

## Metrics Tracked

| Metric | Description |
|---|---|
| `UsageCount` | Number of times each tool was called per agent run. |
| `FailureRate` | Fraction of calls that failed (0.0–1.0) per agent run. |
| `Runtime` | Wall-clock execution time per individual tool call (seconds). |