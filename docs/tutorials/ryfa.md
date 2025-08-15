# How to Run Your First Agent

Once you have defined your agent class you can then run your work flow and see results!

To begin you just have to use `call` for asynchronous flows or `call_sync` if it's a sequential flow. You simply pass your agent node as a parameter as well as the prompt as `user_input`:


### Example
=== "Asynchronous"
    ```python
    --8<-- "docs/scripts/byfa.py:call"
    ```

=== "Synchronous"
    ```python

    --8<-- "docs/scripts/byfa.py:call_sync"

    ```

!!! info "Asynchronous Execution"
    Since the `call` function is asynchronous and needs to be awaited, you should ensure that you are running this code within an asynchronous context like the `main` function in the code snippet above.

    **Jupyter Notebooks**: If you are using in a notebook, you can run the code in a cell with `await` directly.

Just like that you have run your first agent!

---

!!! info "Dynamic Runtime Configuration"

    If you pass `llm_model` to `agent_node` and then a different llm model to either `call` or `call_sync` functions, RailTracks will use the latter one. If you pass `system_message` to `agent_node` and then another `system_message` to either `call` or `call_sync`, the system messages will be stacked.

    ??? example
        ```python
            --8<-- "docs/scripts/byfa.py:imports"

            --8<-- "docs/scripts/byfa.py:weather_response"

            --8<-- "docs/scripts/byfa.py:first_agent"

            --8<-- "docs/scripts/byfa.py:dynamic_prompts"
        ```
        In this example RailTracks will use claude rather than chatgpt and the `system_message` will become
        `"You are a helpful assistant that answers weather-related questions. If not specified, the user is talking about Vancouver."`

---

## Retrieving the Results of a Run

All agents return a response object which you can use to get the last message or the entire message history if you would prefer.

!!! info "Reponse of a Run"
    === "Unstructured Response"
        In the __unstructured response__ example, the last message from the agent and the entire message history can be accessed using the `text` and `message_history` attributes of the response object, respectively.
        
        ```python
        print(f"Last Message: {response.text}")
        print(f"Message History: {response.message_history}")
        ```

    === "Structured Response"

        !!! example inline end "WeatherResponse"

            ```python
            --8<-- "docs/scripts/byfa.py:weather_response"
            ```
        In the structured response example, the `output_schema` parameter is used to define the expected output structure. The response can then be accessed using the `structured` attribute.
        
        ```python
        print(f"Condition: {response.structured.condition}")
        print(f"Temperature: {response.structured.temperature}")
        ```