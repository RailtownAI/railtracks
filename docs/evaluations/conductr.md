## Retrieving Agent Runs
If you have used [**Conductr**](https://conductr.ai/platform/agent-management-suite/agent-observability/) to store your agent runs, you can directly utilize them and perform evaluations by following the simple steps in the snippet below:

```python
--8<-- "docs/scripts/evaluations/conductr.py:get"
```

## Sending Evaluations
Similar to sending your agent runs to **Conductr**, you can upload your agent evaluations by passing the `upload_agent_evaluation` to the `evaluation` function.

```python
--8<-- "docs/scripts/evaluations/conductr.py:send_evals"
```

???+ info "Required API Keys"
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