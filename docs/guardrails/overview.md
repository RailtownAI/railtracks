# Guardrails Overview

Guardrails in Railtracks are a policy layer around agent execution. They let you inspect requests before they reach a model and inspect responses before they are returned, so you can enforce application-specific rules for safety, reliability, and product behavior. In this sense, guardrails are not just about blocking unsafe content; they are also a way to normalize inputs, redact sensitive data, enforce domain limits, or shape outputs in a controlled and observable way.

<!---
The important distinction in Railtracks is that guardrails are separate from tool contracts. A tool contract belongs to the tool itself and describes intrinsic constraints, such as valid argument shapes or protected file paths. Guardrails are different: they are cross-cutting policies that sit above individual tools or models, can be swapped per application, and can be composed centrally as part of an agent definition.
-->

The design direction for Railtracks groups guardrails into four categories: LLM input guardrails, LLM output guardrails, tool call guardrails, and tool response guardrails. This keeps the model simple across the full lifecycle of an agent run: what goes into the model, what comes out of it, what the model tries to execute, and what tools return back into the system. Today, the public API is already shaped with that broader model in mind, even though support is intentionally being rolled out in smaller phases.

| Category | What it governs | Status today |
|----------|------------------|--------------|
| LLM input guardrails | Messages before the model call | Supported |
| LLM output guardrails | The model response before it is returned | Supported |
| Tool call guardrails | Model-proposed tool calls | Planned |
| Tool response guardrails | Tool results flowing back into the agent loop | Planned |

From the user side, guardrails are attached directly where agents are defined. The main entry point is `agent_node(..., guardrails=Guard(...))`, where `Guard` groups the rails you want to run, such as `input=[...]` and `output=[...]`. Custom rules stay Python-native: you can subclass `InputGuard` or `OutputGuard`, inspect the guardrail event, and return an explicit decision to allow, transform, or block.

At the moment, Railtracks supports LLM input and LLM output guardrails for non-tool-calling agents. That includes the main `agent_node` path for terminal, streaming terminal, structured, and streaming structured agents, with input rails running before the LLM call and output rails running after the response is produced. If a guardrail blocks the interaction, Railtracks raises `GuardrailBlockedError` so the outcome stays explicit rather than being silently absorbed.

The next section, [Quickstart](quickstart.md), walks through the minimal setup for attaching a guard to an agent and seeing a real request pass or block in practice.

