The **`RuntimeEvaluator`** reports the wall-clock duration of complete agent invocations. Use it to compare end-to-end flow performance across models, tools, and agent configurations instead of measuring individual LLM or tool calls.

## Usage

```python
--8<-- "docs/scripts/evaluations/runtime_evaluator.py"
```

## Metric Tracked

| Metric | Description |
|---|---|
| `Runtime` | Wall-clock execution time per agent invocation (seconds). |

Runs without a recorded runtime are omitted from the metric instead of being reported as zero. The evaluation payload includes minimum, maximum, mean, median, mode, and standard deviation across measured invocations for visualization.
