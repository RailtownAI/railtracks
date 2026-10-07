## Sequential Flows

In many cases you just want things to happen in a specific order. Instead of letting the LLM decide the order you chain tasks programmatically.

In the below colab notebook, we will explore how to built a simple sequential flow. Connecting an agent in a sequence

Sequential Flows

Run this tutorial interactively in Google Colab.

[Open in Colab →](https://colab.research.google.com/drive/18KkqiC1Vk9YStnhu02WyH24yezizcO9o?usp=sharing)

## Validation Loops

Anyone who has spent time building agentic systems has likely run into the limits of one-shot LLM responses, especially as tasks grow more complex where precision is at a premium. This is where validation loops become useful.

A validation loop allows an agent to iteratively evaluate its own output, apply feedback, and try again until a desired bar is met. In this tutorial, we’ll walk through a simple example of building a validation loop in Railtracks. While the example uses an LLM to perform validation, the same pattern can be applied with fully programmatic checks such as schema validation, static analysis, code execution, or other custom logic.

Agent Validation Loop Tutorial

Run this tutorial interactively in Google Colab.

[Open in Colab →](https://colab.research.google.com/drive/19r_cH3j6Pz74dvWaRku8TtEWAL_Y4v2R?usp=sharing)
