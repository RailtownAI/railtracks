# Sequential Flows
A **Sequential Flow** is a [Flow](../../../documentation/invocation/flows.md) architecture in which Python code invokes nodes in a fixed order, usually passing one node's output to the next. "Sequential" describes the execution order; it is not a separate Railtracks class or API.

Use a Sequential Flow when later tasks depend on earlier results or when the order must remain deterministic instead of being chosen by an LLM. Because the order lives in ordinary Python, you can also add validation, branching, or parallel sections where the application requires them.

## Example

Given two [Agent Nodes](../../../documentation/agent_design/overview.md#agent-node), an async function node can compose them with [Direct Invocation](../../../documentation/invocation/call.md):

```python
import railtracks as rt

from my_agents import ResearchAgent, WriterAgent


@rt.function_node
async def research_then_write(topic: str):
    notes = await rt.call(ResearchAgent, topic)
    return await rt.call(WriterAgent, notes.content)


flow = rt.Flow(name="ResearchThenWrite", entry_point=research_then_write)
report = flow.invoke("How do heat pumps work?")
```

The second call cannot begin until the first `await` returns, so the dependency and execution order are explicit. The Flow makes this composed entry point reusable.

## Try it in Colab

The notebook below walks through a complete Sequential Flow interactively.


<div class="colab-card">


  <div class="colab-card-content">
    <div class="colab-card-title">
      Sequential Flows
    </div>

    <div class="colab-card-description">
      Run this tutorial interactively in Google Colab.
    </div>
  </div>

  <div class="colab-card-action">
    <a
      href="https://colab.research.google.com/drive/18KkqiC1Vk9YStnhu02WyH24yezizcO9o?usp=sharing"
      target="_blank"
      rel="noopener"
      class="colab-button"
    >
      Open in Colab →
    </a>
  </div>
</div>



