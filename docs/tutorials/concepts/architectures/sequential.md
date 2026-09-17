# Sequential Flows

A **sequential flow** is a [Flow](../../../documentation/invocation/flows.md) whose [entry point](../../../documentation/invocation/flows.md#entry-point) is your own `async` function, so its steps run in the order your Python code awaits them. The order lives in the code rather than in a model's judgement: the second step cannot begin before the first returns, because it is a plain `await`.

Reach for one whenever the order is a property of the problem rather than a decision to be made: research before drafting, validate before writing to disk, fetch before summarizing. Leaving that ordering to an LLM adds a decision that can go wrong, spends a round trip on it, and makes a run harder to reproduce. Keep the model for the steps that genuinely need judgement and let the sequence around them stay deterministic.

The tradeoff is flexibility. A sequential flow takes the same path every time, so when the right next step depends on what the last one turned up, either branch in Python once the condition is something you can express in code, or give an [agent node](../../../documentation/agent_design/overview.md#agent-node) the tools and let it choose.

## Example

Two agents composed in order inside a [function node](../../../documentation/agent_design/tools/function_tools.md#what-a-function-node-is), which the Flow then uses as its entry point:

```python
--8<-- "docs/scripts/documentation/sequential.py:sequential"
```

`Writer` cannot start until the `await` on `Researcher` returns, so the dependency between the two steps is explicit, and every `invoke` of the Flow runs the same two steps in the same order. Steps that do *not* depend on each other need not wait at all: gather those concurrently instead, as described in [Direct Invocation](../../../documentation/invocation/call.md).

## Try it in Colab

The notebook below builds a sequential flow interactively.

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



