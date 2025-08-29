LLMs are powerful, but they’re not perfect. They’ll trip over simple reasoning tasks that humans can do without thinking. Railtracks is an agentic framework that makes it easier build more intelligent systems.

Lets get up and running by connecting to an LLM. 

### 1. Installation

```bash title="Install Libraries"
pip install railtracks
pip install railtracks-cli
```

### 2. Define Your Tools and Agents

```python
--8<-- "docs/scripts/quickstart.py:setup"
```
??? Question "Supported Models"
    Railtracks supports many of the most popular model providers. See the [full list](../llm_support/providers.md)

### 3. Run Your Agent

=== "Asynchronous"

    ```python
    --8<-- "docs/scripts/quickstart.py:async_main"
    ```
!!! example "Output"
    The legacy of Artificial Intelligence is an enduring testament to mankind's insatiable quest for knowledge and mastery over complexity, a digital odyssey that wields the twin-edged sword of innovation and ethical quandary, reshaping the shores of possibility whilst casting long shadows yet to be fully unveiled.
    

??? tip "Jupyter Notebooks"
    Jupyter Notebooks run in an event loop already so you should use await directly:
    ```python 
    await rt.call(...)
    ```
### 4. Visualize the Run


```bash title="Initialize Visualizer (Run Once)"
railtracks init
```

```bash title="Run Visualizer"
railtracks viz
```

![RailTracks Visualization](../assets/visualizer_photo.png)

This will open a web interface showing the execution flow, node interactions, and performance metrics of your agentic system.

!!! Tip "To Learn More..."
    If you are new to "agents":

    - [What is an Agent?](../tutorials/guides/agents.md)
    - [What is a Tool?](../tutorials/guides/tools.md)
    
    Or if you are looking to dive right in:

    - [Building your First Agent](../tutorials/byfa.md)
    - [Running your First Agent](../tutorials/ryfa.md)



And just like that, you're up and running. Happy building!