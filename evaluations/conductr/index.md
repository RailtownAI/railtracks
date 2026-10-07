## Retrieving Agent Runs

If you have used [**Conductr**](https://conductr.ai/platform/agent-management-suite/agent-observability/) to store your agent runs, you can directly utilize them and perform evaluations by following the simple steps in the snippet below:

```python
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
```

## Sending Evaluations

Similar to sending your agent runs to **Conductr**, you can upload your agent evaluations by passing the `upload_agent_evaluation` to the `evaluation` function.

```python
from railtownai import upload_agent_evaluation

results = evals.evaluate(
    data=data,
    evaluators=evaluators,
    payload_callback=upload_agent_evaluation, # Your evals will be sent to Conductr automatically
)
```

To let Conductr trigger these evaluations for you, see [Hosted Evaluations](https://docs.railtracks.org/evaluations/conductr_hosted/index.md).

## Categorical Metrics with Status

When your evaluations include a [`Categorical`](https://docs.railtracks.org/evaluations/metrics/categorical/index.md) metric, you can signal to Conductr each label as a **pass**, **fail**, or **partial** outcome. Attach a `status` to each `Category`.

```python
quality = evals.metrics.Categorical(
    name="Quality",
    categories=[
        evals.metrics.Category(name="great", status="pass"),
        evals.metrics.Category(name="ok", status="partial"),
        evals.metrics.Category(name="bad", status="fail"),
        "unrated",  # plain strings still work; status defaults to None
    ],
)
```

`status` must be one of `"pass"`, `"fail"`, `"partial"`, or `None` (the default). Plain-string categories remain supported and are treated as unstatused.

Required API Keys

You will need the following keys set up on your project for the above

### Retreiving Agent Runs

```bash
CONDUCTR_PROJECT_PAT="..."
CONDUCTR_PROJECT_ID="..."
RAILTOWN_API_KEY="..."
```

### Sending Agent Evaluations

```bash
RAILTOWN_API_KEY="..."
EVALUATIONS_API_TOKEN=".."
```

Please refer to your **Conductr** project page at <https://cndr.railtown.ai/> for more info.
