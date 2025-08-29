LLMs are powerful, but they’re not perfect. They’ll trip over simple reasoning tasks that humans can do without thinking. Railtracks is an agentic framework that makes it easier build more intelligent systems.

A classic example is asking an LLM to count characters in a word. The infamous one is: “How many r’s are in strawberry?” See below how easy it is to build a tool in Railtracks that fixes this problem.

### Step 1: Install the Library

```bash
# Core library
pip install railtracks

# [Optional] CLI support for development and visualization
pip install railtracks-cli
```

### Step 2: Define Your Tools and Agents

```python
--8<-- "docs/scripts/quickstart.py:setup"
```

### Step 3: Run Your Agent

=== "Asynchronous"

    ```python
    --8<-- "docs/scripts/quickstart.py:async_main"
    ```
!!! tip "Jupyter Notebooks"
    If you're using Jupyter Notebooks, you can run the code in a cell with `await` directly with the `async main` function.
    For more info on using `async/await` in RT, see [Async/Await in Python](../tutorials/guides/async_await.md).
!!! example "Output"
    ```bash
    LLMResponse(The word "Tyrannosaurus" contains a total of 5 vowels: 2 'a's, 1 'o', and 2 'u's.)
    ```
### Step 4: \[Optional] Visualize the Run

??? tip "Initializing the Visualizer"
    If you haven't run the visualizer before, you will need to initialize the CLI first:

    ```bash
    railtracks init
    ```

```bash
railtracks viz
```

![RailTracks Visualization](../assets/visualizer_photo.png)


This will open a web interface showing the execution flow, node interactions, and performance metrics of your agentic system.

And just like that, you're up and running. Happy building!