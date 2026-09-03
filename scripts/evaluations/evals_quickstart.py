# --8<-- [start: tutorial]
import railtracks as rt
from railtracks import evaluations as evals

# load the data
data = evals.extract_agent_data_points(".railtracks/data/sessions/")

# Default Evaluators
t_evaluator = evals.ToolUseEvaluator()
llm_evaluator = evals.LLMInferenceEvaluator()

# Configurable Evaluators
judge_evaluator = evals.JudgeEvaluator(
    llm=rt.llm.OpenAILLM(model_name="gpt-5.2"),
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
# --8<-- [end: tutorial]
