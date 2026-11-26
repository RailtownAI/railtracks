# Evaluations

Evaluations in `railtracks` are a useful tool to analyze, aggregate, and finally visualize agent runs invoked previously. Sessions are automatically stored in `.railtracks/data/sessions`, so evaluations can be run at any time after invoking your agent. Railtracks locates the `.railtracks` directory by walking up from your current working directory, so the right data is found regardless of which subdirectory you run from.

## Evaluation Definition

```python
import railtracks as rt
from railtracks import evaluations as evals

# load the data
data = evals.extract_agent_data_points(".railtracks/data/sessions/")

# Default Evaluators
t_evaluator = evals.ToolUseEvaluator()
llm_evaluator = evals.LLMInferenceEvaluator()

# Configurable Evaluators
judge_evaluator = evals.JudgeEvaluator(
    llm=rt.llm.OpenAILLM(model_name="gpt-6-luna"),
    metrics=[
        evals.metrics.Categorical(
            name="Helpfulness",
            description=(
                "How helpful was the agent's response in addressing "
                "the user's query or completing the task? Consider "
                "factors such as relevance, accuracy, and completeness."
            ),
            categories=["Not Helpful", "Somewhat Helpful", "Very Helpful"],
        ),
        evals.metrics.Categorical(
            name="Efficiency",
            description=(
                "How efficiently did the agent complete the task? "
                "Consider factors such as speed, resource usage, "
                "and overall effectiveness."
            ),
            categories=["Not Efficient", "Somewhat Efficient", "Very Efficient"],
        ),
    ],
    reasoning=True,
)

results = evals.evaluate(
    data=data,
    evaluators=[t_evaluator, llm_evaluator, judge_evaluator],
)
```

As long as you have previously run an agent using `railtracks`, the script above will then prompt you with:

```console
Multiple agents found in the data:
  0: WebsearchAgent -> 5 data points
  1: FinanceAgent -> 5 data points

Select agent index(es) (comma-separated), or -1 to evaluate all:
```

Upon selection, the results of the evaluation are automatically saved to your `.railtracks/data/evaluations` folder. You can then run `railtracks viz` to open the [legacy visualizer](https://docs.railtracks.org/observability/agenthub/local/index.md) and analyze the results.
