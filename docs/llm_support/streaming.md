# Streaming

## What Is Streaming?

Streaming is a way to make your agent feel more responsive. Instead of waiting for the complete response, you can stream intermediate results as they arrive.


## Streaming Support
Railtracks supports streaming responses from your agent. To interact with a stream, just set the appropriate flag when creating your LLM.

```python
--8<-- "docs/scripts/streaming.py:streaming_flag"
```

When you call the LLM, it will return a generator that you can iterate through:

```python
--8<-- "docs/scripts/streaming.py:streaming_usage"
```

## Agent Support

Agents in Railtracks also support streamed responses. When creating your agent, you provide an LLM with streaming enabled:

```python
--8<-- "docs/scripts/streaming.py:streaming_with_agents"
```

The output of the agent will be a generator containing a sequence of strings, followed by the complete message.

!!! Example "Usage"
    ```python    
    --8<-- "docs/scripts/streaming.py:streaming_agent_usage"
    ```
    `

!!! Warning
    When using streaming, you should fully exhaust the returned object within the session. If you do this outside of the session, the visualizer suite will not work as expected.

!!! Warning 
    Streaming is only supported for tool-calling agents if you are using openai.



