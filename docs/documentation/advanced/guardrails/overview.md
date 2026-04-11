# Guardrails Overview

Guardrails are a policy layer around agent execution. They inspect requests before they reach a model and responses before they are returned, letting you enforce rules for safety, reliability, and product behavior.

Guardrails aren't just about blocking unsafe content. They can also:

- Normalize inputs
- Redact sensitive data
- Enforce domain limits
- Shape outputs in a controlled, observable way

## Categories

Railtracks organizes guardrails into four categories covering the full lifecycle of an agent run:

- **LLM input guardrails**: inspect messages before the model call
- **LLM output guardrails**: inspect the model response before it is returned
- **Tool call guardrails**: validate model-proposed tool calls *(coming soon)*
- **Tool response guardrails**: inspect tool results flowing back into the agent loop *(coming soon)*

## Usage

Guardrails are attached where agents are defined. The main entry point is `agent_node(..., guardrails=Guard(...))`, where `Guard` groups the rails you want to run via `input=[...]` and `output=[...]`.

To write a custom rule, subclass `InputGuard` or `OutputGuard` and implement `__call__`. Your implementation receives an `LLMGuardrailEvent` (the messages and, for output guards, the model response) and returns a `GuardrailDecision` with an action: `ALLOW`, `TRANSFORM`, or `BLOCK`.

!!! info "Current Guardrail Support"
    Railtracks currently supports LLM input and output guardrails for non-tool-calling agents. This covers the `agent_node` path for terminal, streaming terminal, structured, and streaming structured agents. Input rails run before the LLM call; output rails run after. If a guardrail blocks the interaction, Railtracks raises `GuardrailBlockedError` so the outcome stays explicit.

The next section, [Quickstart](quickstart.md), walks through attaching a guard to an agent and seeing a request pass or block in practice.
