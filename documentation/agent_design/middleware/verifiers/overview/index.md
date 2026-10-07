# Verifiers

Human-in-the-loop (HIL) isn't a separate feature in Railtracks — it's `pre_verifier` and `post_verifier`, two node middleware that gate a call with any callable you provide. Where the human (or policy, or second model call) actually sits is entirely up to that callable; Railtracks only handles the gating.

```python
from railtracks.prebuilt.middleware import pre_verifier, post_verifier
```

## Pre vs. post

|                                                         | Gates                                             | `approve_fn` signature                                                                | On decline                                                             |
| ------------------------------------------------------- | ------------------------------------------------- | ------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| `pre_verifier(approve_fn, *, timeout=None, name=None)`  | The call itself, **before** the node runs         | `approve_fn(*args, **kwargs)` (the node's own arguments)                              | The node's body never executes                                         |
| `post_verifier(approve_fn, *, timeout=None, name=None)` | The call's **output**, after the node already ran | `approve_fn(result, *args, **kwargs)` (`result` first, then the node's own arguments) | The call already happened; only the result is stopped from propagating |

Both return a node middleware you attach via `middleware=[...]`, and both accept sync or async `approve_fn`s.

## `Verdict`

Both verifiers require `approve_fn` to return a `Verdict`, imported from `railtracks.middleware`:

```python
from railtracks.middleware import Verdict, VerifierRejectedError
```

| Field             | Meaning                                                                                                                                                               |
| ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `accepted`        | `True` to let the call through, `False` to decline it                                                                                                                 |
| `comment`         | Optional; logged on accept, used as the `VerifierRejectedError` message on decline                                                                                    |
| `args` / `kwargs` | Set on accept to override what gets forwarded into the node call. Only `pre_verifier` reads these back; `post_verifier` ignores them, since the call already happened |
| `result`          | Set on accept to override what propagates onward. Only `post_verifier` reads this back; `pre_verifier` ignores it, since there's no result yet                        |

How `approve_fn`'s arguments relate to the wrapped node

`approve_fn` always receives the exact `*args`/`**kwargs` the node is about to be invoked with at that middleware layer, regardless of which override fields it sets on the returned `Verdict`. That's not necessarily the original call-site arguments if an outer `pre_verifier` already overrode them.

- `pre_verifier`'s `approve_fn(*args, **kwargs)` sees what's about to be forwarded onward (to the node, or to the next inner middleware). If its `Verdict` sets `args`/`kwargs`, those replace what gets forwarded.
- `post_verifier`'s `approve_fn(result, *args, **kwargs)` sees the `result` the node actually produced, plus the same `args`/`kwargs` the node was called with, already reflecting any override from an outer `pre_verifier`.
- When both wrap the same node, list order decides which is outer: `pre_verifier` listed first means it can rewrite the arguments before `post_verifier` (and the node) ever see them. See [Middleware Ordering](https://docs.railtracks.org/documentation/agent_design/middleware/overview/#middleware-ordering).

`Verdict` is generic over `result`'s type (`Verdict[_R]`), matching the wrapped node's return type, so a `result=` override of the wrong type is a type-checker error. There's no equivalent runtime check on `args`/`kwargs`: a bad override surfaces as a `TypeError` from the node call itself.

A declined verdict raises `VerifierRejectedError`. For `pre_verifier` this prevents the node from running at all; for `post_verifier` the node has already run, so decline only stops the result from propagating; it can't undo the call.

### Timeouts

If `approve_fn` doesn't respond within `timeout` seconds, the call is treated as declined with `comment="timeout"`.

### Any callable works

`approve_fn` can be anything matching the signature above: a fixed threshold, a lookup against an internal service, an LLM call, or a real human at a terminal or behind a webhook. Composing backends — a cheap automatic check that only escalates to a human when needed — is common and needs nothing special: it's just one `approve_fn` that calls another. See the [Tutorials](#guided-walkthroughs) below for worked examples of an LLM-as-reviewer and a webhook-based approval flow.

## Usage

```python
import railtracks as rt
from railtracks.middleware import Verdict
from railtracks.prebuilt.middleware import pre_verifier


def approve_refund(order_id: str, amount: float) -> Verdict:
    ok = amount <= 100
    return Verdict(accepted=ok, comment=None if ok else "over the auto-approve limit")


@rt.function_node(middleware=[pre_verifier(approve_refund)])
def refund(order_id: str, amount: float) -> str:
    """Refund an order."""
    return f"refunded {amount} for {order_id}"


refund_flow = rt.Flow(name="pre_verifier demo", entry_point=refund)

# refund_flow.invoke(order_id="A1", amount=50)     -> "refunded 50 for A1"
# refund_flow.invoke(order_id="A2", amount=500)    -> raises VerifierRejectedError
```

```python
from railtracks.prebuilt.middleware import post_verifier


# `result` must be the first positional parameter -- checked eagerly, at
# post_verifier(...) call time, not on first invocation.
def redact_ssn(result: dict, query: str) -> Verdict[dict]:
    scrubbed = {k: v for k, v in result.items() if k != "ssn"}
    return Verdict(accepted=True, comment="redacted SSN", result=scrubbed)


@rt.function_node(middleware=[post_verifier(redact_ssn)])
def lookup_customer(query: str) -> dict:
    """Look up a customer record."""
    return {"name": "Jane Doe", "ssn": "000-00-0000", "query": query}


lookup_flow = rt.Flow(name="post_verifier demo", entry_point=lookup_customer)

# lookup_flow.invoke(query="Jane Doe") -> {"name": "Jane Doe", "query": "Jane Doe"}
```

`post_verifier`'s `approve_fn` must take `result` first

This is checked eagerly, when `post_verifier(...)` is called, not deferred to the first invocation. Getting the signature wrong (e.g. `def approve(query, result)` instead) raises `TypeError` immediately, naming what was found instead of `result`.

Both can gate the same node: the request is approved going in, then the result is confirmed coming out.

```python
def approve_request(order_id: str, amount: float) -> Verdict:
    return Verdict(accepted=True, comment="looks fine")


def confirm_result(result: str, order_id: str, amount: float) -> Verdict:
    return Verdict(accepted=True)


@rt.function_node(
    middleware=[
        pre_verifier(approve_request, name="approve_request"),
        post_verifier(confirm_result, name="confirm_result"),
    ]
)
def refund_with_both(order_id: str, amount: float) -> str:
    """Refund an order, approved going in and confirmed coming out."""
    return f"refunded {amount} for {order_id}"


both_flow = rt.Flow(name="pre+post verifier demo", entry_point=refund_with_both)
```

## Composing with other middleware

Verifiers compose with any other node middleware through the normal `middleware=[...]` list. Ordering matters; see [Middleware Ordering](https://docs.railtracks.org/documentation/agent_design/middleware/overview/#middleware-ordering) for the general rule. A common case is `post_verifier` placed *outside* `Retry`: the reviewer only sees the final settled result, not every retry attempt.

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

For end-to-end scenarios (an LLM enforcing written policy as the reviewer, and approvals resolved asynchronously via a webhook), see the Tutorials:

- [Human-in-the-Loop: LLM Reviewers](https://docs.railtracks.org/tutorials/walkthroughs/hil_llm_reviewer/index.md)
- [Human-in-the-Loop: Webhook Approvals](https://docs.railtracks.org/tutorials/walkthroughs/hil_webhook_approval/index.md)

Runnable versions of these and other verifier patterns (composing a cheap auto-approve with a human escalation, a barebones chat-loop sketch) live under [`examples/human_in_the_loop/`](https://github.com/RailtownAI/railtracks/tree/main/examples/human_in_the_loop).
