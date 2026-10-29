# Sequential Flows

A **sequential flow** is a [Flow](https://docs.railtracks.org/documentation/invocation/flows/index.md) whose [entry point](https://docs.railtracks.org/documentation/invocation/flows/#entry-point) is your own `async` function, so its steps run in the order your Python code awaits them. The order lives in the code rather than in a model's judgement: the second step cannot begin before the first returns, because it is a plain `await`.

Reach for one whenever the order is a property of the problem rather than a decision to be made: research before drafting, validate before writing to disk, fetch before summarizing. Leaving that ordering to an LLM adds a decision that can go wrong, spends a round trip on it, and makes a run harder to reproduce. Keep the model for the steps that genuinely need judgement and let the sequence around them stay deterministic.

The tradeoff is flexibility. A sequential flow takes the same path every time, so when the right next step depends on what the last one turned up, either branch in Python once the condition is something you can express in code, or give an [agent node](https://docs.railtracks.org/documentation/agent_design/overview/#agent-node) the tools and let it choose.

## Example

Two agents composed in order inside a [function node](https://docs.railtracks.org/documentation/agent_design/tools/function_tools/#what-a-function-node-is), which the Flow then uses as its entry point:

```python
import railtracks as rt

llm = rt.llm.OpenAILLM("gpt-5.4-mini")

Researcher = rt.agent_node(
    name="Researcher",
    system_message="Collect the key facts about the topic the user gives you. Answer in bullet points.",
    llm=llm,
)

Writer = rt.agent_node(
    name="Writer",
    system_message="Turn the notes you are given into a single tight paragraph.",
    llm=llm,
)


@rt.function_node
async def research_then_write(topic: str) -> str:
    """Research a topic, then write the findings up as a paragraph.

    Args:
        topic: The subject to research.

    Returns:
        A one paragraph write-up of the topic.
    """
    notes = await rt.call(Researcher, topic)
    write_up = await rt.call(Writer, notes.text)
    return write_up.text


flow = rt.Flow(name="Research then Write", entry_point=research_then_write)
result = flow.invoke("How do heat pumps work?")
```

`Writer` cannot start until the `await` on `Researcher` returns, so the dependency between the two steps is explicit, and every `invoke` of the Flow runs the same two steps in the same order. Steps that do *not* depend on each other need not wait at all: gather those concurrently instead, as described in [Direct Invocation](https://docs.railtracks.org/documentation/invocation/call/index.md).

## Try it in Colab

The notebook below builds a sequential flow interactively.

Sequential Flows

Run this tutorial interactively in Google Colab.

[Open in Colab →](https://colab.research.google.com/drive/18KkqiC1Vk9YStnhu02WyH24yezizcO9o?usp=sharing)
