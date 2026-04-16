## Adding a Structured Output
Now that you've seen how to add tools. Let's look at your agent can respond with reliable typed outputs. Schemas give you reliable, machine-checked outputs you can safely consume in code, rather than brittle strings.


```python 
--8<-- "docs/scripts/first_agent.py:weather_response"

--8<-- "docs/scripts/first_agent.py:first_agent_model"
```

??? tip "Pydantic: Defining a Schema"
    We use [Pydantic](https://pydantic.dev/docs/validation/latest/get-started/) to define structured data models.
    ```python
    --8<-- "docs/scripts/first_agent.py:general_structured"
    ```
    Visit the [pydantic docs](https://docs.pydantic.dev/latest/) to learn about what you can do with `BaseModel`'s

## Structured + Tool Calling
Often you will want the best of both worlds, an agent capable of both tool calling and responding in a structured format. At the time of writing this, most LLMs do not support _structured output_ and _tool calling_ together. In `Railtracks` we support the following two ways of achieving this:

### 1. Implement the Separation
Using a [Flow](../invocation/flows.md) you can separate out the tool calling and strucutred output steps. Here's an example how:

```python
async def flow_func(arg: str)->str:
    first_resp = await rt.call(ToolCallingAgent, arg)

    second_resp = await rt.call(StructuredAgent, first_step.message_history) # or pass in first_step.content
```
!!! warning "`ToolCallingAgent` vs `StructuredAgent`"
    As noted in the first section of this page, the pure `TooCallingAgent` should **_not_** be passed an `output_schema` for things to work optimally this way, and similarly the `StructuredAgent` should not have `tool_nodes` passed to it.

### 2. Abstracted Separation
In this way, Railtracks automatically implements the steps above for you. Simply need provide the `output_schema` and `tool_nodes` parameter to the same `agent_node` definition.
```python 
--8<-- "docs/scripts/first_agent.py:first_agent_all"
```