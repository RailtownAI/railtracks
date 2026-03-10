The **`JudgeEvaluator`** uses an LLM as a judge to score agent outputs against a set of [`CategoricalMetric`](../metrics/categorical.md)s. For each data point and each metric, it sends the agent's input/output to the judge LLM and records its verdict.

!!! note
    `JudgeEvaluator` only accepts `Categorical` metrics. Passing a `Numerical` metric will log a warning and skip it.

## Usage

```python
from railtracks import evaluation as eval
import railtracks as rt

relevance = eval.metrics.Categorical(
    name="Relevance",
    categories=["Relevant", "Irrelevant"],
)

sentiment = eval.metrics.Categorical(
    name="Sentiment",
    categories=["Positive", "Negative", "Neutral"],
)

judge = eval.JudgeEvaluator(
    llm=rt.llm.OpenAILLM(model_name="gpt-4o"),
    metrics=[relevance, sentiment],
    reasoning=True,  # include the judge's reasoning in results
)
```

## Parameters

| Parameter | Description |
|---|---|
| `llm` | The LLM used as the judge. |
| `metrics` | Metrics to evaluate. |
| `system_prompt` | Override the default judge system prompt. |
| `timeout` | Timeout (seconds) for the judge flow. |
| `reasoning` | If `True`, the judge LLM also returns reasoning per result. |
| `verbose`  | Log progress per data point. |

## Custom System Prompt

By default, `JudgeEvaluator` uses a built-in prompt that instructs the LLM to score agent quality. You can override it to focus on your domain:

```python
judge = eval.JudgeEvaluator(
    llm=rt.llm.OpenAILLM(model_name="gpt-4o"),
    metrics=[relevance],
    system_prompt="You are a financial analyst. Evaluate whether the agent's response is accurate and compliant with regulations.",
)
```

## Results

For each metric the evaluator produces one `MetricResult` per data point, plus an aggregate breakdown across categories. When `reasoning=True`, a corresponding `{metric_name}_reasoning` result is also stored alongside each verdict.