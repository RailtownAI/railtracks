In this quickstart, you’ll install Railtracks, run your first agent, and visualize its execution; all in a few minutes.

## 1. Installation

```bash title="Install Library"
pip install railtracks
pip install 'railtracks[visual]'
```
!!! note 
    `railtracks[visual]` is optional, but required for the visualization step.


## 2. Running your Agent

Define an [agent](../agent_design/overview.md#agent-node) with a model and system message, wrap it in a [Flow](../invocation/flows.md), then invoke it with a prompt:

```python
--8<-- "docs/scripts/documentation/quickstart.py:setup"
```

!!! example "Example Output"
    Your exact output will vary depending on the model.
    ``` title="Example Response"
    Hello! I can help you out with a wide range of tasks...
    ``` 

???+ Warning "No API key set?"
    Make sure you are calling a model you have an API key set in your `.env` file. 

    ```txt title=".env"
    OPENAI_API_KEY="..."
    ANTHROPIC_API_KEY="..."
    ```

    Railtracks supports many of the most popular model providers. See the [full list](../../integrations/llms/providers.md)

???+ tip "Jupyter Notebooks"
    If you’re running this in a Jupyter notebook, remember that notebooks already run inside an event loop. In that case, use `await flow.ainvoke(...)` instead of `flow.invoke(...)`. Head to [Async/Await](../../tutorials/concepts/async_await.md) for more on _async_ features in Python. 
   
## 3. Visualize the Run
With Railtracks CLI you can dive deep on your runs. Our observability runs locally from the command line. 

!!! tip "Setup"    

    ```bash title="Install CLI Tool"
    pip install 'railtracks[visual]'
    ```


    ```bash title="Initialize UI and Start"
    railtracks init
    railtracks viz --beta
    ```

    ```bash title="Update the UI given new releases"
    railtracks update --beta
    ```

![A run opened in the current visualizer](https://railtracksstorage.blob.core.windows.net/railtrackswebsite/images/v2-visualizer/session-details-light.png#only-light)
![A run opened in the current visualizer](https://railtracksstorage.blob.core.windows.net/railtrackswebsite/images/v2-visualizer/session-details-dark.png#only-dark)

This opens a web interface at `http://localhost:3031` with all of your agent runs. Open a run to step through every node it called, with the messages each agent sent, token usage, and cost. See [Local Visualization (Current)](../../observability/agenthub/local_v2.md) for a full tour, or the [legacy visualizer](../../observability/agenthub/local.md) (`railtracks viz`) to browse evaluation results.
