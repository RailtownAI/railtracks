# Verifiers

Human-in-the-loop (HIL) isn't a separate feature in Railtracks — it's `pre_verifier` and `post_verifier`, two node middleware that gate a call with any callable you provide. Where the human (or policy, or second model call) actually sits is entirely up to that callable; Railtracks only handles the gating.

```python
from railtracks.prebuilt.middleware import pre_verifier, post_verifier
```

## Pre vs. post

| | Gates | `approve_fn` signature | On decline |
|---|---|---|---|
| `pre_verifier(approve_fn, *, timeout=None, name=None)` | The call itself, **before** the node runs | `approve_fn(*args, **kwargs)` — the node's own arguments | The node's body never executes |
| `post_verifier(approve_fn, *, timeout=None, name=None)` | The call's **output**, after the node already ran | `approve_fn(result, *args, **kwargs)` — `result` first, then the node's own arguments | The call already happened; only the result is stopped from propagating |

Both return a node middleware you attach via `middleware=[...]`, and both accept sync or async `approve_fn`s.

!!! info "How `approve_fn`'s arguments relate to the wrapped node"
    `approve_fn` always receives the exact `*args`/`**kwargs` the node is about to be invoked with at that middleware layer — not necessarily the original call-site arguments, if an outer `pre_verifier` already overrode them.

    - `pre_verifier`'s `approve_fn(*args, **kwargs)` sees what's about to be forwarded onward (to the node, or to the next inner middleware). If its `Verdict` sets `args`/`kwargs`, those replace what gets forwarded.
    - `post_verifier`'s `approve_fn(result, *args, **kwargs)` sees the `result` the node actually produced, plus the same `args`/`kwargs` the node was called with — already reflecting any override from an outer `pre_verifier`.
    - When both wrap the same node, list order decides which is outer: `pre_verifier` listed first means it can rewrite the arguments before `post_verifier` (and the node) ever see them. See [Middleware Ordering](../overview.md#middleware-ordering).

## Usage

```python
--8<-- "docs/scripts/verifiers.py:pre_verifier_basic"
```

```python
--8<-- "docs/scripts/verifiers.py:post_verifier_basic"
```

!!! warning "`post_verifier`'s `approve_fn` must take `result` first"
    This is checked eagerly, when `post_verifier(...)` is called, not deferred to the first invocation. Getting the signature wrong (e.g. `def approve(query, result)` instead) raises `TypeError` immediately, naming what was found instead of `result`.

Both can gate the same node — the request is approved going in, then the result is confirmed coming out:

```python
--8<-- "docs/scripts/verifiers.py:composed"
```

## `Verdict`

Both verifiers require `approve_fn` to return a `Verdict`, imported from `railtracks.middleware`:

```python
from railtracks.middleware import Verdict, VerifierRejectedError
```

| Field | Meaning |
|---|---|
| `accepted` | `True` to let the call through, `False` to decline it |
| `comment` | Optional; logged on accept, used as the `VerifierRejectedError` message on decline |
| `args` / `kwargs` | Set on accept to override what gets forwarded into the node call. Only `pre_verifier` reads these back — `post_verifier` ignores them, since the call already happened |
| `result` | Set on accept to override what propagates onward. Only `post_verifier` reads this back — `pre_verifier` ignores it, since there's no result yet |

Both verifiers' `approve_fn` receives the node's original `args`/`kwargs` as input (see the signatures above) regardless of which override fields it sets on the returned `Verdict`.

`Verdict` is generic over `result`'s type (`Verdict[_R]`), matching the wrapped node's return type — a `result=` override of the wrong type is a type-checker error. There's no equivalent runtime check on `args`/`kwargs`: a bad override surfaces as a `TypeError` from the node call itself.

A declined verdict raises `VerifierRejectedError`. For `pre_verifier` this prevents the node from running at all; for `post_verifier` the node has already run, so decline only stops the result from propagating — it can't undo the call.

### Timeouts

If `approve_fn` doesn't respond within `timeout` seconds, the call is treated as declined with `comment="timeout"`.

### Any callable works

`approve_fn` can be anything matching the signature above: a fixed threshold, a lookup against an internal service, an LLM call, or a real human at a terminal or behind a webhook. Composing backends — a cheap automatic check that only escalates to a human when needed — is common and needs nothing special: it's just one `approve_fn` that calls another. See the [Tutorials](#guided-walkthroughs) below for worked examples of an LLM-as-reviewer and a webhook-based approval flow.

## Composing with other middleware

Verifiers compose with any other node middleware through the normal `middleware=[...]` list. Ordering matters — see [Middleware Ordering](../overview.md#middleware-ordering) for the general rule. A common case is `post_verifier` placed *outside* `Retry`: the reviewer only sees the final settled result, not every retry attempt.

```python
import railtracks as rt
from railtracks.middleware import Verdict
from railtracks.prebuilt.middleware import Retry, post_verifier


def confirm_settled_result(result: str, order_id: str, amount: float) -> Verdict:
    return Verdict(accepted=True)


@rt.function_node(
    middleware=[
        post_verifier(confirm_settled_result, name="confirm_settled_result"),
        Retry(3),
    ]
)
def refund_with_retry(order_id: str, amount: float) -> str:
    return f"refunded {amount} for {order_id}"
```

Placing `post_verifier` *inside* `Retry` instead would re-run the review on every attempt, including ones whose result is discarded.

## Guided walkthroughs

For end-to-end scenarios — an LLM enforcing written policy as the reviewer, and approvals resolved asynchronously via a webhook — see the Tutorials:

- [Human-in-the-Loop: LLM Reviewers](../../../../tutorials/walkthroughs/hil_llm_reviewer.md)
- [Human-in-the-Loop: Webhook Approvals](../../../../tutorials/walkthroughs/hil_webhook_approval.md)

Runnable versions of these and other verifier patterns (composing a cheap auto-approve with a human escalation, a barebones chat-loop sketch) live under [`examples/human_in_the_loop/`](https://github.com/RailtownAI/railtracks/tree/main/examples/human_in_the_loop).
