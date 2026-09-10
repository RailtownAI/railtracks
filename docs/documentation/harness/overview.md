# Agent Harness

## What is an agent harness?

An **agent harness** is the code that surrounds a model call. The model brings judgment; the harness brings everything else: the loop that keeps calling it, the tools it can reach, what lands in its context, the limits on what it is allowed to do, and the record of what it actually did. Change your model tomorrow and the harness is what you still own, which is what makes it the part worth owning outright.

Railtracks is an agent harness framework. Every part of that list is an ordinary Python object you assemble yourself, so an agentic harness here is code you can read, step through in a debugger, and unit test; not a runtime you configure from the outside.

## The five parts

| Part | Question it answers | Railtracks primitives |
|---|---|---|
| **Loop** | When does the agent keep going, and when is it done? | [`rt.agent_node`](../agent_design/overview.md) runs the tool-calling loop; [`rt.Flow`](../invocation/flows.md) and [`rt.call`](../invocation/call.md) drive multi-step work |
| **Tool surface** | What can the agent actually do? | [`rt.function_node`](../agent_design/tools/function_tools.md), [`rt.ToolManifest`](../agent_design/tools/agents_as_tools.md), [`rt.connect_mcp`](../agent_design/tools/mcp.md) |
| **Context** | What does the model see on this turn? | `system_message`, [`rt.context`](../advanced/context.md), [`ToDoToolSet`](../agent_design/tools/prebuilt/todos.md), [`KeyValueMemoryToolSet`](../agent_design/tools/prebuilt/key_value_memory.md), [retrieval](../../retrieval/runtime/quickstart.md) |
| **Controls** | What is it allowed to do, and how much of it? | [`middleware=` / `model_middleware=`](../agent_design/middleware/overview.md): `MaxCalls`, `Timeout`, `Retry`, `Lock`, [verifiers](../agent_design/middleware/verifiers/overview.md), [guardrails](../agent_design/middleware/guardrails/overview.md) |
| **Record** | What happened, and can I replay it? | session state, [`railtracks viz`](../../observability/agenthub/local.md), [`rt.evaluations.evaluate`](../../evaluations/quickstart.md) |

The sections below build one harness up part by part: a repository assistant that reads code, plans its work, and runs shell commands only with permission.

## 1. The loop

An agent with tools is already a loop: the model proposes a tool call, the tool runs, the result goes back into the conversation, and it repeats until the model answers instead of calling a tool. `rt.agent_node` owns that loop, so the smallest useful harness is a model, a prompt, and one tool.

```python
--8<-- "docs/scripts/documentation/harness.py:loop"
```

`rt.Flow` is the entry point that runs it: it opens a session, tracks state, and applies run-wide settings like `timeout` and `context`. Inside a node, `rt.call` invokes another node directly, which is how you nest loops (an agent that delegates to sub-agents) or write the outer loop yourself in plain Python when a tool-calling loop is the wrong shape.

## 2. The tool surface

The tool surface *is* the agent's capability. Nothing else in the harness matters as much: an agent with a shell tool can do anything the shell can, and an agent with only a read tool cannot damage anything. Any Python function becomes a tool, and its signature and docstring become the schema the model sees.

```python
--8<-- "docs/scripts/documentation/harness.py:tools"
```

`run_shell` above is deliberately left as a plain function rather than a `@rt.function_node`, because a shell tool should not reach the model without a gate on it. Section 4 wraps it before it is handed to an agent.

Two things to get right here:

- **Keep the surface small.** Every tool is context the model spends on every turn and another path it can pick wrongly. Prefer three sharp tools over ten overlapping ones.
- **Write docstrings for the model, not for reviewers.** The docstring is the prompt for that tool. Say when to use it, what the arguments mean, and what it returns.

Tools do not have to be functions you wrote. [Agents-as-tools](../agent_design/tools/agents_as_tools.md) puts a whole sub-harness behind a single tool call, and [MCP](../agent_design/tools/mcp.md) pulls in tool servers you did not write.

## 3. Context

The model is stateless. Everything it "knows" on a given turn was put there by the harness, and context is finite, so a harness has to decide what earns a place in it. Railtracks gives you three levers:

- **`system_message`** is the standing instructions. Assemble it from parts rather than hardcoding one string; toolsets ship their own guidance via `prompt()`.
- **Tool-mediated state** lets the agent read and write its own working memory instead of pushing everything into the prompt. `ToDoToolSet` gives it a plan it can revise; `KeyValueMemoryToolSet` gives it facts that survive the run.
- **`rt.context`** holds run-scoped values your Python code sets and reads, invisible to the model unless you inject them.

```python
--8<-- "docs/scripts/documentation/harness.py:context"
```

For large corpora the answer is retrieval rather than a bigger prompt: see the [Retrieval Runtime](../../retrieval/runtime/quickstart.md).

## 4. Controls

Controls are what make a harness safe to point at real systems. In Railtracks they are middleware, applied at two boundaries: `middleware=` wraps the whole node (one call in, one result out) and `model_middleware=` wraps each individual model call inside the loop. The distinction matters for budgets: `MaxCalls(40)` as node middleware allows forty invocations of the agent, while the same thing as model middleware allows forty raw model calls. Either way the counter is cumulative for the life of the agent you attached it to, not per run: a second `invoke` of the same agent inherits whatever it already spent. `agent_node` copies the middleware you hand it, so the budget belongs to that agent, and rebuilding the agent is what gives you a fresh one.

```python
--8<-- "docs/scripts/documentation/harness.py:controls"
```

The pieces worth knowing:

| Control | What it does |
|---|---|
| [`pre_verifier`](../agent_design/middleware/verifiers/overview.md) | Gates a call **before** it runs. The approval function is any callable: an allowlist, a policy service, another model, or a human at a terminal or webhook. Declining means the tool body never executes. |
| [`post_verifier`](../agent_design/middleware/verifiers/overview.md) | Gates or rewrites a call's **result** after it ran. Use it to redact, or to confirm output before it propagates. |
| `MaxCalls` | Hard cap on invocations, so a confused agent cannot loop forever on your budget. |
| `Timeout` | Wall-clock deadline on a call. |
| `Retry` | Re-runs transient failures with backoff. |
| `Lock` | Serialises access to something that cannot take concurrent calls. |
| [Guardrails](../agent_design/middleware/guardrails/overview.md) | `input_guard` and `output_guard` checks on what goes into and comes out of the model. |

Middleware order is significant: the first entry in the list is the outermost. `pre_verifier` listed before `Timeout` means approval happens outside the deadline, so time spent waiting on a human does not count against the tool's own timeout.

The general rule is to place each control at the narrowest boundary that still catches the problem. Gating the individual shell tool, as above, leaves the agent free to read files without interruption while still requiring a human for anything that mutates state.

## 5. The record

A harness you cannot inspect is a harness you cannot improve. Runs are recorded as session state, so `railtracks viz` replays the full request graph locally: every tool call, its arguments, token usage, and where time went. That same recorded data is what [evaluations](../../evaluations/quickstart.md) score, which is how you tell whether a prompt or tool change actually helped.

```python
--8<-- "docs/scripts/documentation/harness.py:record"
```

## How much harness do you need?

Scale the controls to the blast radius of the tools, not to the sophistication of the agent.

| Tool surface | Minimum harness |
|---|---|
| Read-only (search, retrieval, public APIs) | Turn budget and timeout. Little else can go wrong. |
| Writes to systems you own (files, internal databases, tickets) | Add a verifier on the mutating tools, and record every run. |
| Writes with external effects (payments, emails, production infrastructure) | Human approval on mutating tools, guardrails on inputs and outputs, and an audit trail you can hand to someone else. |

## Harness patterns

- **Coding harness** uses read, edit, and shell tools, a todo list so multi-file work survives across turns, and an allowlist plus human approval on anything that mutates the working tree. See [`examples/harness/`](https://github.com/RailtownAI/railtracks/tree/main/examples/harness).
- **Research harness** uses search and fetch tools, retrieval over what has been gathered, key-value memory for findings, and a structured-output agent at the end to force the report into a schema. See [Structured Output](../agent_design/structured_extraction.md).
- **Operations harness** uses a small number of high-consequence tools, each behind `pre_verifier` with a real approver, `Lock` on anything that cannot run concurrently, and a full record of who approved what. See the [Human-in-the-Loop walkthroughs](../../tutorials/walkthroughs/hil_webhook_approval.md).

!!! info "Not an evaluation harness"
    "Harness" is also used for benchmark runners that score a model on a fixed task set. This page is about the *agent* harness: the production scaffolding a model runs inside. For scoring agent behaviour, see [Evaluations](../../evaluations/preface.md).

## Next steps

- [Quickstart](../getting_started/quickstart.md) to install and run your first agent.
- [Agent Design](../agent_design/overview.md) for the agent layer in detail.
- [Middleware](../agent_design/middleware/overview.md) for the full control catalogue.
- [Flows](../invocation/flows.md) for wiring multi-agent harnesses.
- [Observability](../../observability/agenthub/local.md) for inspecting and replaying runs.
