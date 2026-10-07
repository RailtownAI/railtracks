# Agent Harness

## What is an agent harness?

An **agent harness** is the code that surrounds a model call. The model brings judgment; the harness brings everything else: the loop that keeps calling it, the tools it can reach, what lands in its context, the limits on what it is allowed to do, and the record of what it actually did. Change your model tomorrow and the harness is what you still own, which is what makes it the part worth owning outright.

Railtracks is an agent harness framework. Every part of that list is an ordinary Python object you assemble yourself, so an agentic harness here is code you can read, step through in a debugger, and unit test; not a runtime you configure from the outside.

## The five parts

| Part             | Question it answers                                  | Railtracks primitives                                                                                                                                                                                                                                                                                                                                                                                                    |
| ---------------- | ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Loop**         | When does the agent keep going, and when is it done? | [`rt.agent_node`](https://docs.railtracks.org/documentation/agent_design/overview/index.md) runs the tool-calling loop; [`rt.Flow`](https://docs.railtracks.org/documentation/invocation/flows/index.md) and [`rt.call`](https://docs.railtracks.org/documentation/invocation/call/index.md) drive multi-step work                                                                                                       |
| **Tool surface** | What can the agent actually do?                      | [`rt.function_node`](https://docs.railtracks.org/documentation/agent_design/tools/function_tools/index.md), [`rt.ToolManifest`](https://docs.railtracks.org/documentation/agent_design/tools/agents_as_tools/index.md), [`rt.connect_mcp`](https://docs.railtracks.org/documentation/agent_design/tools/mcp/index.md)                                                                                                    |
| **Context**      | What does the model see on this turn?                | `system_message`, [`rt.context`](https://docs.railtracks.org/documentation/advanced/context/index.md), [`ToDoToolSet`](https://docs.railtracks.org/documentation/agent_design/tools/prebuilt/todos/index.md), [`KeyValueMemoryToolSet`](https://docs.railtracks.org/documentation/agent_design/tools/prebuilt/key_value_memory/index.md), [retrieval](https://docs.railtracks.org/retrieval/runtime/quickstart/index.md) |
| **Controls**     | What is it allowed to do, and how much of it?        | [`middleware=` / `model_middleware=`](https://docs.railtracks.org/documentation/agent_design/middleware/overview/index.md): `MaxCalls`, `Timeout`, `Retry`, `Lock`, [verifiers](https://docs.railtracks.org/documentation/agent_design/middleware/verifiers/overview/index.md), [guardrails](https://docs.railtracks.org/documentation/agent_design/middleware/guardrails/overview/index.md)                             |
| **Record**       | What happened, and can I replay it?                  | the event stream, [`railtracks viz --beta`](https://docs.railtracks.org/observability/agenthub/local_v2/index.md), [`rt.evaluations.evaluate`](https://docs.railtracks.org/evaluations/quickstart/index.md)                                                                                                                                                                                                              |

The sections below build one harness up part by part: a repository assistant that reads code, plans its work, and runs shell commands only with permission.

## 1. The loop

An agent with tools is already a loop: the model proposes a tool call, the tool runs, the result goes back into the conversation, and it repeats until the model answers instead of calling a tool. `rt.agent_node` owns that loop, so the smallest useful harness is a model, a prompt, and one tool.

```python
from pathlib import Path

import railtracks as rt


@rt.function_node
def read_file(path: str) -> str:
    """Read a UTF-8 text file from disk.

    Args:
        path (str): Path of the file to read.
    """
    return Path(path).read_text(encoding="utf-8")


RepoReader = rt.agent_node(
    name="Repo Reader",
    llm=rt.llm.AnthropicLLM("claude-sonnet-5-5"),
    system_message="You answer questions about a repository. Read files before you answer.",
    tool_nodes=[read_file],
)

reader_flow = rt.Flow("repo-reader", entry_point=RepoReader)
answer = reader_flow.invoke("What package name does pyproject.toml declare?")
print(answer.content)
```

`rt.Flow` is the entry point that runs it: it opens a session, tracks state, and applies run-wide settings like `timeout` and `context`. Inside a node, `rt.call` invokes another node directly, which is how you nest loops (an agent that delegates to sub-agents) or write the outer loop yourself in plain Python when a tool-calling loop is the wrong shape.

## 2. The tool surface

The tool surface *is* the agent's capability. Nothing else in the harness matters as much: an agent with a shell tool can do anything the shell can, and an agent with only a read tool cannot damage anything. Any Python function becomes a tool, and its signature and docstring become the schema the model sees.

```python
import shlex
import subprocess


@rt.function_node
def list_files(directory: str) -> list[str]:
    """List the file names directly inside a directory.

    Args:
        directory (str): Directory to list.
    """
    return sorted(p.name for p in Path(directory).iterdir())


# Left as a plain function on purpose: section 4 wraps it with a permission gate.
def run_shell(command: str) -> str:
    """Run a shell command and return its combined output.

    Args:
        command (str): Command to run, as it would be typed in a terminal.
    """
    finished = subprocess.run(
        shlex.split(command),
        capture_output=True,
        text=True,
        timeout=60,
    )
    return f"exit={finished.returncode}\n{finished.stdout}{finished.stderr}"
```

`run_shell` above is deliberately left as a plain function rather than a `@rt.function_node`, because a shell tool should not reach the model without a gate on it. Section 4 wraps it before it is handed to an agent.

Two things to get right here:

- **Keep the surface small.** Every tool is context the model spends on every turn and another path it can pick wrongly. Prefer three sharp tools over ten overlapping ones.
- **Write docstrings for the model, not for reviewers.** The docstring is the prompt for that tool. Say when to use it, what the arguments mean, and what it returns.

Tools do not have to be functions you wrote. [Agents-as-tools](https://docs.railtracks.org/documentation/agent_design/tools/agents_as_tools/index.md) puts a whole sub-harness behind a single tool call, and [MCP](https://docs.railtracks.org/documentation/agent_design/tools/mcp/index.md) pulls in tool servers you did not write.

## 3. Context

The model is stateless. Everything it "knows" on a given turn was put there by the harness, and context is finite, so a harness has to decide what earns a place in it. Railtracks gives you three levers:

- **`system_message`** is the standing instructions. Assemble it from parts rather than hardcoding one string; toolsets ship their own guidance via `prompt()`.
- **Tool-mediated state** lets the agent read and write its own working memory instead of pushing everything into the prompt. `ToDoToolSet` gives it a plan it can revise; `KeyValueMemoryToolSet` gives it facts that survive the run.
- **`rt.context`** holds run-scoped values your Python code sets and reads, invisible to the model unless you inject them.

```python
todos = rt.prebuilt.tools.ToDoToolSet()
memory = rt.prebuilt.tools.KeyValueMemoryToolSet()

HARNESS_SYSTEM_MESSAGE = "\n\n".join(
    [
        "You are a repository assistant. Read before you write, and verify with tests.",
        rt.prebuilt.tools.ToDoToolSet.prompt(),
        rt.prebuilt.tools.KeyValueMemoryToolSet.prompt(),
    ]
)
```

For large corpora the answer is retrieval rather than a bigger prompt: see the [Retrieval Runtime](https://docs.railtracks.org/retrieval/runtime/quickstart/index.md).

## 4. Controls

Controls are what make a harness safe to point at real systems. In Railtracks they are middleware, applied at two boundaries: `middleware=` wraps the whole node (one call in, one result out) and `model_middleware=` wraps each individual model call inside the loop. The distinction matters for budgets: `MaxCalls(40)` as `model_middleware` caps the agent at forty model calls inside one run, which is how you stop a tool-calling loop from spinning. Counters do not carry across runs, so every `invoke` starts from a full budget.

Put budgets in `model_middleware=`, not `middleware=`

Node middleware is rebuilt on every invocation, so a `MaxCalls` counter in the `middleware=` slot resets each time and never reaches its limit. Use `model_middleware=` for budgets until [issue #1560](https://github.com/RailtownAI/railtracks/issues/1560) is resolved.

```python
import asyncio

from railtracks.middleware import Verdict
from railtracks.prebuilt.middleware import MaxCalls, Timeout, pre_verifier

ALLOWED_EXECUTABLES = {"git", "ls", "pytest", "ruff"}


async def approve_shell(command: str) -> Verdict:
    """Allowlist the executable, then ask a human about the specific command."""
    parts = shlex.split(command)
    if not parts or parts[0] not in ALLOWED_EXECUTABLES:
        return Verdict(accepted=False, comment=f"{command!r} is not on the allowlist")

    # approve_fn runs on the event loop, so never block it with a bare input()
    answer = await asyncio.to_thread(input, f"Run `{command}`? [y/N] ")
    if answer.strip().lower() == "y":
        return Verdict(accepted=True)
    return Verdict(accepted=False, comment="declined by the operator")


gated_shell = rt.function_node(
    run_shell,
    name="run_shell",
    middleware=[pre_verifier(approve_shell), Timeout(90)],
)
```

The pieces worth knowing:

| Control                                                                                                          | What it does                                                                                                                                                                                              |
| ---------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`pre_verifier`](https://docs.railtracks.org/documentation/agent_design/middleware/verifiers/overview/index.md)  | Gates a call **before** it runs. The approval function is any callable: an allowlist, a policy service, another model, or a human at a terminal or webhook. Declining means the tool body never executes. |
| [`post_verifier`](https://docs.railtracks.org/documentation/agent_design/middleware/verifiers/overview/index.md) | Gates or rewrites a call's **result** after it ran. Use it to redact, or to confirm output before it propagates.                                                                                          |
| `MaxCalls`                                                                                                       | Hard cap on invocations, so a confused agent cannot loop forever on your budget.                                                                                                                          |
| `Timeout`                                                                                                        | Wall-clock deadline on a call.                                                                                                                                                                            |
| `Retry`                                                                                                          | Re-runs transient failures with backoff.                                                                                                                                                                  |
| `Lock`                                                                                                           | Serialises access to something that cannot take concurrent calls.                                                                                                                                         |
| [Guardrails](https://docs.railtracks.org/documentation/agent_design/middleware/guardrails/overview/index.md)     | `input_guard` and `output_guard` checks on what goes into and comes out of the model.                                                                                                                     |

Middleware order is significant: the first entry in the list is the outermost. `pre_verifier` listed before `Timeout` means approval happens outside the deadline, so time spent waiting on a human does not count against the tool's own timeout.

The general rule is to place each control at the narrowest boundary that still catches the problem. Gating the individual shell tool, as above, leaves the agent free to read files without interruption while still requiring a human for anything that mutates state.

## 5. The record

A harness you cannot inspect is a harness you cannot improve. Every run is recorded as an event stream, so `railtracks viz --beta` replays the full request graph locally: every tool call, its arguments, token usage, middleware decisions, and where time went. That same recorded data is what [evaluations](https://docs.railtracks.org/evaluations/quickstart/index.md) score, which is how you tell whether a prompt or tool change actually helped.

```python
RepoHarness = rt.agent_node(
    name="Repo Harness",
    llm=rt.llm.AnthropicLLM("claude-sonnet-5-5"),
    system_message=HARNESS_SYSTEM_MESSAGE,
    tool_nodes=[
        read_file,
        list_files,
        gated_shell,
        *todos.tool_set(),
        *memory.tool_set(),
    ],
    middleware=[Timeout(600)],
    model_middleware=[MaxCalls(40, custom_message="model call budget exhausted")],
)

harness_flow = rt.Flow(
    "repo-harness",
    entry_point=RepoHarness,
    context={"repo_root": "."},
)


async def run_harness() -> None:
    outcome = await harness_flow.ainvoke(
        "Find the slowest unit test and explain why it is slow."
    )
    print(outcome.content)
    # every ToDoToolSet read is async, pretty_dashboard included
    print(await todos.pretty_dashboard())


asyncio.run(run_harness())
```

## How much harness do you need?

Scale the controls to the blast radius of the tools, not to the sophistication of the agent.

| Tool surface                                                               | Minimum harness                                                                                                      |
| -------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| Read-only (search, retrieval, public APIs)                                 | Turn budget and timeout. Little else can go wrong.                                                                   |
| Writes to systems you own (files, internal databases, tickets)             | Add a verifier on the mutating tools, and record every run.                                                          |
| Writes with external effects (payments, emails, production infrastructure) | Human approval on mutating tools, guardrails on inputs and outputs, and an audit trail you can hand to someone else. |

## Harness patterns

- **Coding harness** uses read, edit, and shell tools, a todo list so multi-file work survives across turns, and an allowlist plus human approval on anything that mutates the working tree. See [`examples/harness/`](https://github.com/RailtownAI/railtracks/tree/main/examples/harness).
- **Research harness** uses search and fetch tools, retrieval over what has been gathered, key-value memory for findings, and a structured-output agent at the end to force the report into a schema. See [Structured Output](https://docs.railtracks.org/documentation/agent_design/structured_extraction/index.md).
- **Operations harness** uses a small number of high-consequence tools, each behind `pre_verifier` with a real approver, `Lock` on anything that cannot run concurrently, and a full record of who approved what. See the [Human-in-the-Loop walkthroughs](https://docs.railtracks.org/tutorials/walkthroughs/hil_webhook_approval/index.md).

Not an evaluation harness

"Harness" is also used for benchmark runners that score a model on a fixed task set. This page is about the *agent* harness: the production scaffolding a model runs inside. For scoring agent behaviour, see [Evaluations](https://docs.railtracks.org/evaluations/preface/index.md).

## Next steps

- [Quickstart](https://docs.railtracks.org/documentation/getting_started/quickstart/index.md) to install and run your first agent.
- [Agent Design](https://docs.railtracks.org/documentation/agent_design/overview/index.md) for the agent layer in detail.
- [Middleware](https://docs.railtracks.org/documentation/agent_design/middleware/overview/index.md) for the full control catalogue.
- [Flows](https://docs.railtracks.org/documentation/invocation/flows/index.md) for wiring multi-agent harnesses.
- [Observability](https://docs.railtracks.org/observability/agenthub/local_v2/index.md) for inspecting and replaying runs.
