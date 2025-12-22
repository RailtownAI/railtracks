from railtracks import evaluation as evals

# Initialize the evaluation dataset
dataset = evals.data.EvaluationDataset(
    path=".railtracks/data/agent_data",
)

evaluator = evals.evaluators.ToolUseEvaluator()
evaluator.run(dataset.data_points)