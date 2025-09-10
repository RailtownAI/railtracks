Large Language Models (LLMs) are powerful, but they’re not enough on their own.  
Railtracks gives them structure, tools, and visibility so you can build agents that actually get things done.  

In this quickstart, you’ll install Railtracks, run your first agent, and visualize its execution — all in a few minutes.

### 1. Installation

```bash title="Install Library"
pip install railtracks
pip install railtracks-cli
```
!!! note 
    `railtracks-cli` is optional, but required for the visualization step. 


### 2. Running your Agent

Define an agent with a model and system message, then call it with a prompt:

```python
--8<-- "docs/scripts/quickstart.py:setup"
```

!!! example "Example Output"
    Your exact output will vary depending on the model.
    ``` title="Example Response"
    Hello! I can help you out with a wide range of tasks...
    ``` 

??? Question "Supported Models"
    Railtracks supports many of the most popular model providers. See the [full list](../llm_support/providers.md)

??? tip "Jupyter Notebooks"
    If you’re running this in a Jupyter notebook, remember that notebooks already run inside an event loop. In that case, call `await rt.call(...)` directly:
   
### 3. Visualize the Run
Railtracks has a built-in visualizer to inspect and review your agent runs. 

```bash title="Initialize Visualizer (Run Once)"
railtracks init
```

```bash title="Run Visualizer"
railtracks viz
```

![RailTracks Visualization](../assets/visualizer_photo.png)

This will open a web interface showing the execution flow, node interactions, and performance metrics of your agentic system.

----

!!! Tip "Next Steps"
    You’ve got your first agent running! Here’s where to go next:

    **Learn the Basics**
    
    - [What is an Agent?](../background/agents.md)
    - [What is a Tool?](../background/tools.md)
    
    **Build Something**

    - [Building your First Agent](../tutorials/byfa.md)
    - [Running your First Agent](../tutorials/ryfa.md)

