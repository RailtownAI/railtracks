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
    llm=rt.llm.OpenAILLM(model_name="gpt-5.4-mini"),
    metrics=[relevance, sentiment],
    reasoning=True,  # include the judge's reasoning in results
)