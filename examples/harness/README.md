# Harness examples

A harness is the code around the model call: the loop, the tool surface, what goes into context, the controls on what the agent may do, and the record of what it did. These two examples are the same five parts at two different risk levels.

For the concepts behind them, see the [Agent Harness docs](../../docs/documentation/harness/overview.md).

- `minimal_harness.py` -> read-only tools pointed at this repository. Because nothing can mutate state, the only controls it needs are a turn budget (`MaxCalls` as `model_middleware`) and a deadline (`Timeout`). Start here.
- `coding_harness.py` -> file writes and shell commands, each behind `pre_verifier`. Adds path confinement to a scratch workspace, an executable allowlist, and operator approval on every mutating call, plus a `ToDoToolSet` plan and `KeyValueMemoryToolSet` facts. This is the shape a coding agent takes.

## Running them

```bash
uv run python examples/harness/minimal_harness.py
uv run python examples/harness/coding_harness.py
```

Both need a provider key in your `.env` (`OPENAI_API_KEY` for the minimal harness, `ANTHROPIC_API_KEY` for the coding harness). Override the model with `HARNESS_MODEL`, and the coding harness' scratch directory with `HARNESS_WORKSPACE`.

Both run with `save_state=True`, so `railtracks viz` replays the full request graph afterwards; every tool call, its arguments, and where the time went.

## Where the controls come from

| Piece | Import | Used for |
|---|---|---|
| `MaxCalls` | `railtracks.prebuilt.middleware` | Capping turns so a confused agent cannot loop on your budget |
| `Timeout` | `railtracks.prebuilt.middleware` | Wall-clock deadline on a tool or on the whole agent |
| `pre_verifier` | `railtracks.prebuilt.middleware` | Gating a call before it runs; the approver is any callable |
| `Verdict` | `railtracks.middleware` | What an approval function returns |
| `ToDoToolSet`, `KeyValueMemoryToolSet` | `rt.prebuilt.tools` | Letting the agent manage its own plan and facts |

`coding_harness.py` gates the individual write and shell tools rather than the agent as a whole, which is the general rule: put each control at the narrowest boundary that still catches the problem. Reads stay uninterrupted; anything that mutates state stops for a human.

For more verifier shapes (LLM reviewers, webhook approvals, composing an automatic check that escalates to a human), see [`../human_in_the_loop/`](../human_in_the_loop/README.md).
