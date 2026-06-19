
# --8<-- [start: get]
import railtownai
from railtracks import evaluations as evals

# Select your agent run ids:
AGENT_RUN_IDS: list[str] = [
"ID_1",
"ID_2",
]

# Retrieve the agent runs
payload = railtownai.get_agent_runs(AGENT_RUN_IDS, skip_errors=True)

# extract `AgentDataPoint`s
data = evals.extract_agent_data_points(payload)

# Continue with evaluations as before
# --8<-- [end: get]

t_evaluator = evals.ToolUseEvaluator()
llm_evaluator = evals.LLMInferenceEvaluator()
evaluators = [t_evaluator, llm_evaluator]

# --8<-- [start: send_evals]
from railtownai import upload_agent_evaluation

results = evals.evaluate(
    data=data,
    evaluators=evaluators,
    payload_callback=upload_agent_evaluation, # Your evals will be sent to Conductr automatically
)
# --8<-- [end: send_evals]
import railtracks
SomeAgent = railtracks.agent_node()

# --8<-- [start: send_runs]
import railtracks as rt
from railtownai import upload_agent_run

my_flow = rt.Flow(
    "Flow Name",
    entry_point=SomeAgent,
    payload_callback=upload_agent_run # Your runs will be sent to Conductr automatically
)
# --8<-- [end: send_runs]
