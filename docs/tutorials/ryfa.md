# How to Run Your First Agent

Once you have defined your agent class ([Build Your First Agent](byfa.md)), you need to execute it. Railtracks provides two modern approaches for running agents: **Flow** (recommended) and **`@rt.session` decorator**.

## Using Flow (Recommended)

The **`Flow`** class provides the cleanest way to package and execute your agent workflows. It automatically manages sessions and provides both sync and async execution methods.

```python
import railtracks as rt

# Define your agent entry point
@rt.function_node
async def main(message: str):
    result = await rt.call(WeatherAgent, message)
    return result

# Create a Flow
flow = rt.Flow("Weather Flow", entry_point=main)

# Run synchronously
result = flow.invoke("What's the weather in Paris?")
print(result.text)
```

!!! tip "Async Notebooks"
    If you're in a Jupyter notebook or already inside an async context, use `await flow.ainvoke(...)` instead.

## Using @rt.session Decorator

The **`@rt.session`** decorator automatically wraps your async functions with session management:

```python
import railtracks as rt
import asyncio

@rt.session(
    timeout=60,
    logging_setting="INFO"
)
async def weather_workflow(city: str):
    result = await rt.call(WeatherAgent, f"What's the weather in {city}?")
    return result

# Run the workflow
result, session = asyncio.run(weather_workflow("Paris"))
print(result.text)
```

## Direct Calling (Advanced)

For simple cases, you can call the agent directly in an async context:

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
    Since the **`call`** function is asynchronous and needs to be awaited, you should ensure that you are running this code within an async context (like inside a Flow entry point or `@rt.session` decorated function).

    **Jupyter Notebooks**: If you are using in a notebook, you can run the code in a cell with **`await`** directly.
    
    For more info on using `async/await` in RT, see [Async/Await in Python](../background/async_await.md).

!!! info "Dynamic Runtime Configuration"

    If you pass `llm` to `agent_node` and then a different llm model to `call` function, Railtracks will use the latter one. If you pass `system_message` to `agent_node` and then another `system_message` to `call`, the system messages will be stacked.

    ??? example
        ```python
            --8<-- "docs/scripts/first_agent.py:imports"

            --8<-- "docs/scripts/first_agent.py:weather_response"

            --8<-- "docs/scripts/first_agent.py:first_agent"

            --8<-- "docs/scripts/first_agent.py:dynamic_prompts"
        ```
        In this example Railtracks will use claude rather than chatgpt and the `system_message` will become
        `"You are a helpful assistant that answers weather-related questions. If not specified, the user is talking about Vancouver."`

Just like that you have run your first agent!

---
## Using Sessions (Advanced)

For complex scenarios requiring fine-grained control, you can use the **`rt.Session`** context manager directly:

```python
--8<-- "docs/scripts/first_agent.py:session"
```

!!! note "When to Use Sessions Directly"
    The context manager approach is useful when you need:
    
    - Fine-grained control over session lifecycle
    - To run multiple workflows within the same session context
    - Advanced session management features
    
    For most use cases, prefer **Flow** or **`@rt.session`** decorator for cleaner code.

For more details on session features, see the [Sessions](../advanced_usage/session.md) documentation.

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
            --8<-- "docs/scripts/first_agent.py:weather_response"
            ```
        In the structured response example, the `output_schema` parameter is used to define the expected output structure. The response can then be accessed using the `structured` attribute.
        
        ```python
        print(f"Condition: {response.structured.condition}")
        print(f"Temperature: {response.structured.temperature}")
        ```