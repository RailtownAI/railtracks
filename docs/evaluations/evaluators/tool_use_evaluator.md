The **`ToolUseEvaluator`** assesses the given agent runs provided in the dataset and provides a summary of the different tools invoked, their frequency, and their failure rate.

Its usage is fairly straightforward given with the only requirement being that only the `AgentDataPoint`s in the dataset that have `full` tracing enabled upon saving will provide tool information for this evaluator to assess. Please read [`AgentDataPoint`](../data/agent_data.md) for further information.

```python
dataset = EvaluationDataset(
    path=".railtracks/data/agent_data",
)

evaluator = ToolUseEvaluator()
evaluator.run(dataset.data_points)
```