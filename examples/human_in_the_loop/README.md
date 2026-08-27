# Human-in-the-loop examples

HIL isn't a separate feature -- it's `pre_verifier`/`post_verifier`
(`railtracks.prebuilt.middleware`), gating a node call with any callable
matching `Callable[P, Verdict] | Callable[P, Awaitable[Verdict]]`
(`pre_verifier`) or `Callable[Concatenate[R, P], Verdict[R] | Awaitable[Verdict[R]]]`
(`post_verifier`, where `R` is the wrapped node's return type). Where the
human actually sits is entirely up to `approve_fn` -- these examples show a
few shapes.

For the `Verdict` shape, timeout semantics, and how pre/post compose with
each other and with other middleware (e.g. `Retry`), see the docs (tracked in
#1424, in progress) rather than this README.

- `pre_post_verifier_demo.py` -- the core primitives: `pre_verifier` gating
  whether a call happens at all, `post_verifier` gating/rewriting a call's
  output after it already ran, and both composed on one node.
- `webhook_approval_demo.py` -- register a pending approval, resolve it via
  an external event (standing in for a Slack button / UI callback) by
  setting an `asyncio.Future`'s result from outside the coroutine that's
  awaiting it. The registry lives entirely in user code here.
- `custom_approval_demo.py` -- demonstrates that "custom" isn't a backend to
  build at all: any plain callable matching the `approve_fn` signature works
  with `pre_verifier` as-is. Shows composing backends (auto-approve under a
  threshold, escalate to a human above it).
- `llm_approval_demo.py` -- an LLM applying a written policy as the
  `approve_fn`, the shape most production guardrails actually take: a policy
  check before a refund is processed (pre), a compliance review that rewrites
  a drafted reply after it's generated (post), and both on one node. Makes
  real LLM calls -- needs `OPENAI_API_KEY` (or swap the model in the file).

Run any of the four directly, e.g.:

```bash
uv run python examples/human_in_the_loop/pre_post_verifier_demo.py
```

The first three run standalone -- no real server, webhook, or API key
required. `llm_approval_demo.py` needs `OPENAI_API_KEY`.

## `chat_loop_demo.py` -- exploratory skeleton, not a backend

A different, more speculative sketch than the four above: can `Verdict` +
other middleware drive a continuously-running chat that keeps going, turn
after turn, until the human actually wants to close the session? It's a
barebones skeleton for that question, not a decided pattern -- see the
file's docstring for the design notes (in particular, why ending the chat is
a top-level gated node, and why the agent signals intent to end via an
ordinary tool call rather than structured output). Needs a real LLM call
(`OPENAI_API_KEY`) and runs interactively:

```bash
uv run python examples/human_in_the_loop/chat_loop_demo.py
```
