# --8<-- [start: tutorial]
import railtracks as rt
from railtracks import evaluations as eval

# load the data
data = eval.extract_agent_data_points(".railtracks/data/sessions/")

# Default Evaluators
t_evaluator = eval.ToolUseEvaluator()
llm_evaluator = eval.LLMInferenceEvaluator()

# Configurable Evaluators
m1 = eval.metrics.Categorical(
    name="Sentiment", 
    categories=["Positive", "Negative", "Neutral"]
)

m2 = eval.metrics.Categorical(
    name="Relevance", 
    categories=["Relevant", "Irrelevant"]
)

judge_evaluator = eval.JudgeEvaluator(
    llm=rt.llm.OpenAILLM(model_name="gpt-5.2"),
    system_prompt=None, # Optional system prompt to guide the judge
    metrics=[m1, m2], # Pass in your defined metrics to evaluate on
    reasoning=True, # Whether to include the judge's reasoning
)

results = eval.evaluate(
    data=data,
    evaluators=[t_evaluator, llm_evaluator, judge_evaluator],
)
# --8<-- [end: tutorial]