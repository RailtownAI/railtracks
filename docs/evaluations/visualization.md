# Visualization

After running evaluations, results are automatically saved to `.railtracks/data/evaluations`. The built-in visualizer lets you explore these results locally with no sign up required.

!!! tip "Setting up the visualizer"
    See [Observability → Visualization](../observability/visualization.md) for installation and setup instructions.

## Exploring Evaluation Results

Once the visualizer is running, navigate to the **Evaluations** tab to browse your saved evaluation runs. For each run you can view:

- **Per-metric results** across all evaluated data points
- **Aggregate summaries** (e.g. category distributions for `JudgeEvaluator`, mean token usage for `LLMInferenceEvaluator`)
- **Per-tool breakdowns** for `ToolUseEvaluator` (invocation counts, failure rates, runtimes)

<div style="overflow: hidden; width: 100%; height: 120%;">
    <img src="../../assets/visualizer.gif"/>
</div>
