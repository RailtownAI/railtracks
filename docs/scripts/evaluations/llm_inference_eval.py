from railtracks import evaluations as evals

data = evals.extract_agent_data_points()  # all sessions in the workspace DB

evaluator = evals.LLMInferenceEvaluator()
results = evals.evaluate(data=data, evaluators=[evaluator])