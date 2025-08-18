Build your first agentic system in just a few steps.

### Step 1: Install the Library

```bash
# Core library
pip install railtracks

# [Optional] CLI support for development and visualization
pip install railtracks-cli
```

### Step 2: Define Your Modular Components

```python
--8<-- "docs/scripts/quickstart.py:setup"
```

### Step 3: Run Your Application


=== "Synchronous"

    ```python
    --8<-- "docs/scripts/quickstart.py:synchronous_call"
    ```

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

```bash
railtracks viz
```
??? tip "Initializing the Visualizer"
    If you haven't run the visualizer before, you will need to initialize the CLI first:

    ```bash
    railtracks init
    ```
![RailTracks Visualization](../assets/visualizer_photo.png)

This will open a web interface showing the execution flow, node interactions, and performance metrics of your agentic system.

And just like that, you're up and running. The possibilities are endless.