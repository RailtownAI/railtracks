# Harness examples

A harness is the code around the model call: the loop, the tool surface, what goes into context, the controls on what the agent may do, and the record of what it did. These two examples are the same five parts at two different risk levels.

For the concepts behind them, see the [Agent Harness docs](../../docs/documentation/harness/overview.md).

- `minimal_harness.py` -> read-only tools pointed at this repository. Because nothing can mutate state, the only controls it needs are a model call budget (`MaxCalls` as `model_middleware`) and a deadline (`Timeout`). Start here.
- `coding_harness.py` -> file writes and shell commands, each behind `pre_verifier`. Adds path confinement on `write_file`, an executable allowlist on `run_shell`, and operator approval on every mutating call, plus a `ToDoToolSet` plan and `KeyValueMemoryToolSet` facts. This is the shape a coding agent takes.

> **`run_shell` is not a sandbox.** It sets `cwd` to the workspace, but an interpreter on the allowlist (`python`, or `pytest` running test files the agent just wrote) can reach the rest of the disk. The approval prompt is the real control there, which is why the example asks before every shell call.

## Running them

```bash
uv run python examples/harness/minimal_harness.py
uv run python examples/harness/coding_harness.py
```

Each example hardcodes one provider, so it needs that provider's key in your `.env`: `OPENAI_API_KEY` for the minimal harness, `ANTHROPIC_API_KEY` for the coding harness. `HARNESS_MODEL` overrides the model *id* only, not the provider, so pass an id that provider accepts (`gpt-...` for the minimal harness, `claude-...` for the coding one). Edit the `rt.llm.*` call to switch provider. `HARNESS_WORKSPACE` overrides the coding harness' scratch directory.

Both are recorded by default, so `railtracks viz` replays the full request graph afterwards; every tool call, its arguments, and where the time went.

## Where the controls come from

| Piece | Import | Used for |
|---|---|---|
| `MaxCalls` | `railtracks.prebuilt.middleware` | Capping model calls inside a run so a tool loop cannot spin on your budget. Must go in the `model_middleware=` slot; the node slot does not enforce ([#1560](https://github.com/RailtownAI/railtracks/issues/1560)) |
| `Timeout` | `railtracks.prebuilt.middleware` | Wall-clock deadline on a tool or on the whole agent |
| `pre_verifier` | `railtracks.prebuilt.middleware` | Gating a call before it runs; the approver is any callable |
| `Verdict` | `railtracks.middleware` | What an approval function returns |
| `ToDoToolSet`, `KeyValueMemoryToolSet` | `rt.prebuilt.tools` | Letting the agent manage its own plan and facts |

`coding_harness.py` gates the individual write and shell tools rather than the agent as a whole, which is the general rule: put each control at the narrowest boundary that still catches the problem. Reads stay uninterrupted; anything that mutates state stops for a human.

For more verifier shapes (LLM reviewers, webhook approvals, composing an automatic check that escalates to a human), see [`../human_in_the_loop/`](../human_in_the_loop/README.md).
