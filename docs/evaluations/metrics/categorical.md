Categorical metrics are the recommended metrics to use with Evaluators that are themselves an LLM (or another agent). Research has shown that LLMs inherently struggle with context regarding providing a numerical score for tasks therefore categories (ie "labels") are a more reliable metric. 

In **Railtracks** we mainly use these metrics in [`JudgeEvaluator`](../evaluators/judge_evaluator.md)

## Usage

```python
from railtracks import evaluation as eval

sentiment = eval.metrics.Categorical(
    name="Sentiment",
    categories=["Positive", "Negative", "Neutral"],
    description="Tone of the agent's response.",  # optional
)
```

Pass metrics into a `JudgeEvaluator` to evaluate agent runs against each category.