# Session Management

Sessions in Railtracks manage the execution environment for your flows. The recommended approach is using the **`Flow`** class.

## Using Flow

The **`Flow`** class provides the cleanest abstraction for packaging and executing workflows:

```python
import railtracks as rt

@rt.function_node
async def my_workflow(user_input: str):
    result = await rt.call(MyAgent, user_input)
    return result

# Create and run a Flow
flow = rt.Flow(
    "My Workflow", 
    entry_point=my_workflow,
    timeout=60,
    context={"api_key": "secret"},
    logging_setting="INFO"
)

result = flow.invoke("Hello!")  # Synchronous
# or
result = await flow.ainvoke("Hello!")  # Asynchronous
```

**Benefits:**
- Clean, reusable workflow abstraction
- Automatic session management
- Both sync and async execution methods
- Named workflows for better observability
- Type-safe configuration

### Configuring Your Flow

You can configure various aspects of your Flow:

```python
import railtracks as rt

@rt.function_node
async def my_workflow():
    # Your workflow logic here
    result = await rt.call(MyAgent, "Hello!")
    return result

# Configure timeout, context, logging, etc.
flow = rt.Flow(
    "Configured Workflow",
    entry_point=my_workflow,
    timeout=30,  # 30 second timeout
    context={"user_id": "123"},  # Global context variables
    logging_setting="DEBUG",  # Enable debug logging
    save_state=True,  # Save execution state to file
)
```

### Multiple Workflows

Each Flow gets its own isolated session:

```python
import railtracks as rt

@rt.function_node
async def greet_workflow(name: str):
    result = await rt.call(greet_agent, name)
    return result

@rt.function_node
async def farewell_workflow(name: str):
    result = await rt.call(farewell_agent, name)
    return result

# Create separate Flows
greet_flow = rt.Flow("Greeting", entry_point=greet_workflow, context={"action": "greet"})
farewell_flow = rt.Flow("Farewell", entry_point=farewell_workflow, context={"action": "farewell"})

# Run independently
result1 = greet_flow.invoke("Diana")
result2 = farewell_flow.invoke("Robert")
```

!!! warning "Important Notes"

    - **Entry Point**: The entry point function should be decorated with `@rt.function_node`
    - **Automatic Cleanup**: Flows automatically clean up resources when execution completes
    - **Unique Identifiers**: Each flow gets a unique identifier for tracking and debugging

??? info "More Examples"

    !!! example "Error Handling"
        ```python
        import railtracks as rt
        
        @rt.function_node
        async def safe_workflow():
            try:
                return await rt.call(sample_node)
            except Exception as e:
                print(f"Workflow failed: {e}")
                return None
        
        flow = rt.Flow("Safe Workflow", entry_point=safe_workflow, end_on_error=True)
        ```

    !!! example "API Workflows"
        ```python
        import railtracks as rt
        
        @rt.function_node
        async def api_workflow():
            # Context variables are available to all nodes
            result = await rt.call(sample_node)
            return result
        
        flow = rt.Flow("API Workflow", entry_point=api_workflow, context={"api_key": "secret", "region": "us-west"})
        ```
        
    !!! example "Tracked Execution"
        ```python
        import railtracks as rt
        
        @rt.function_node
        async def daily_report():
            # Execution state saved to .railtracks/daily-report-v1.json
            return await rt.call(sample_node)
        
        flow = rt.Flow("Daily Report", entry_point=daily_report, save_state=True)
        ```