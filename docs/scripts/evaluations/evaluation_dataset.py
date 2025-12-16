import railtracks as rt
from railtracks import evaluation as evals

# --8<-- [start: construct]
dataset = evals.data.EvaluationDataset(
    path="./railtracks/data/agent_run", 
    name="MyEvaluationDataset"
)
# --8<-- [end: construct]

