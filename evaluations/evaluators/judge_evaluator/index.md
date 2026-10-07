The **`JudgeEvaluator`** uses an LLM as a judge to score agent outputs against a set of [`CategoricalMetric`](https://docs.railtracks.org/evaluations/metrics/categorical/index.md)s or [`NumericalMetric`](https://docs.railtracks.org/evaluations/metrics/numerical/index.md)s. For each data point and each metric, it sends the agent's input/output to the judge LLM and records its verdict.

Note

`JudgeEvaluator` only accepts `Categorical` and `Numerical` metrics. Passing any other metric type will log a warning and skip it.

## Usage

```python
from railtracks import evaluations as evals
import railtracks as rt

relevance = evals.metrics.Categorical(
    name="Relevance",
    categories=["Relevant", "Irrelevant"],
)

sentiment = evals.metrics.Categorical(
    name="Sentiment",
    categories=["Positive", "Negative", "Neutral"],
)

judge = evals.JudgeEvaluator(
    llm=rt.llm.OpenAILLM(model_name="gpt-6-luna"),
    metrics=[relevance, sentiment],
    reasoning=True,  # include the judge's reasoning in results
)
```

## Parameters

| Parameter       | Description                                                 |
| --------------- | ----------------------------------------------------------- |
| `llm`           | The LLM used as the judge.                                  |
| `metrics`       | Metrics to evaluate.                                        |
| `system_prompt` | Override the default judge system prompt.                   |
| `timeout`       | Timeout (seconds) for the judge flow.                       |
| `reasoning`     | If `True`, the judge LLM also returns reasoning per result. |
| `verbose`       | Log progress per data point.                                |

## Custom System Prompt

By default, `JudgeEvaluator` uses a built-in prompt that instructs the LLM to score agent quality. You can override it to focus on your domain:

```python
judge = eval.JudgeEvaluator(
    llm=rt.llm.OpenAILLM(model_name="gpt-6-luna"),
    metrics=[relevance],
    system_prompt="You are a financial analyst. Evaluate whether the agent's response is accurate and compliant with regulations.",
)
```

## Results

For each metric the evaluator produces one `MetricResult` per data point, plus an aggregate breakdown across categories. When `reasoning=True`, a corresponding `{metric_name}_reasoning` result is also stored alongside each verdict.
