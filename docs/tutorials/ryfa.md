# How to Run Your First Agent

## Calling the Agent directly
Once you have defined your agent class ([Build Your First Agent](byfa.md)) you can then run your workflow and see results!

To begin you just have to use **`call`** method from RailTracks. This is an asynchronous method so you will need to run it in an async context.

=== "Asynchronous"
    ```python
    --8<-- "docs/scripts/first_agent.py:call"
    ```

!!! tip "Agent input options"
    There are multiple ways to provide input to your agent.
    
    ???+ example "single user message"
        If you'd like to simply provide a single user message, you can pass it as a string directly to the **`call`** 

    ???+ example "few-shot prompting"
        If you want to provide a few-shot prompt, you can pass a list of messages to the `call` functions, with the specific message for each role being passed as an input to its specific role ie (**`rt.llm.UserMessage`** for user, **`rt.llm.AssistantMessage`** for assistant): 
        ```python
        --8<-- "docs/scripts/first_agent.py:fewshot"
        ```
        

!!! info "Asynchronous Execution"
    Since the **`call`** function is asynchronous and needs to be awaited, you should ensure that you are running this code within an asynchronous context like the **`main`** function in the code snippet above.

    **Jupyter Notebooks**: If you are using in a notebook, you can run the code in a cell with **`await`** directly.
    
    For more info on using `async/await` in RT, see [Async/Await in Python](../background/async_await.md).

!!! info "Dynamic Runtime Configuration"

    If you pass `llm` to `agent_node` and then a different llm model to `call` function, RailTracks will use the latter one. If you pass `system_message` to `agent_node` and then another `system_message` to `call`, the system messages will be stacked.

    ??? example
        ```python
            --8<-- "docs/scripts/first_agent.py:imports"

            --8<-- "docs/scripts/first_agent.py:weather_response"

            --8<-- "docs/scripts/first_agent.py:first_agent"

            --8<-- "docs/scripts/first_agent.py:dynamic_prompts"
        ```
        In this example RailTracks will use claude rather than chatgpt and the `system_message` will become
        `"You are a helpful assistant that answers weather-related questions. If not specified, the user is talking about Vancouver."`

Just like that you have run your first agent!

---
## Calling the Agent within a Session
Alternatively, you can run your agent within a session using the **`rt.Session`** context manager. This allows you to manage the session state and run multiple agents or workflows within the same session and providing various options such as setting a timeout, a shared context ([Context](../advanced_usage/context.md)), and more.

```python
--8<-- "docs/scripts/first_agent.py:session"
```

For more details on how to use sessions, please refer to the [Sessions](../advanced_usage/session.md) documentation.
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
            --8<-- "docs/scripts/first_agent.py:weather_response"
            ```
        In the structured response example, the `output_schema` parameter is used to define the expected output structure. The response can then be accessed using the `structured` attribute.
        
        ```python
        print(f"Condition: {response.structured.condition}")
        print(f"Temperature: {response.structured.temperature}")
        ```