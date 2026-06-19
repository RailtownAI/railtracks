from railtracks import evaluations as evals

data = evals.extract_agent_data_points(".railtracks/data/sessions/")

evaluator = evals.LLMInferenceEvaluator()
results = evals.evaluate(data=data, evaluators=[evaluator])