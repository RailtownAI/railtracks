# Human-in-the-Loop: Webhook Approvals

Not every approval backend can respond inline. A real human review often means suspending the flow until an external event -- a Slack button click, a UI callback, a webhook payload -- delivers the decision, arbitrarily far in the future. This walkthrough builds that shape with `pre_verifier`, using an `asyncio.Future` that a separate HTTP route resolves.

The full runnable files are [`examples/human_in_the_loop/webhook_demo/run.py`](https://github.com/RailtownAI/railtracks/blob/main/examples/human_in_the_loop/webhook_demo/run.py) (everything relevant to the pattern) and `webhook_demo/setup.py` (a two-button Streamlit page standing in for a real approval UI -- setup only, not part of what this teaches). It needs `streamlit`:

```bash
uv pip install streamlit
uv run python examples/human_in_the_loop/webhook_demo/run.py
```

Running it opens a browser tab; clicking Approve or Reject sends a real HTTP POST that resolves the pending approval. `localhost` stands in for the public URL a real webhook would be registered at -- nothing else here is simulated.

The excerpts below are abridged for readability. See the linked files for the complete, runnable version.

## Registering a pending approval

`approve_fn` doesn't have to resolve synchronously. Here it creates a `Future`, stores it keyed by the order, and awaits it -- suspending the node call until something else resolves that future:

```python
_pending: dict[str, asyncio.Future] = {}


async def ask_via_webhook(order_id: str, amount: float) -> Verdict:
    future: asyncio.Future = asyncio.get_running_loop().create_future()
    _pending[order_id] = future
    return await future


hil_gate = pre_verifier(ask_via_webhook, timeout=180, name="webhook_hil")
```

`timeout` bounds how long the flow will wait -- if nothing resolves the future in time, `pre_verifier` treats it as a decline with `comment="timeout"`, the same as any other approval backend.

## Resolving it from a webhook route

A FastAPI route is what actually delivers the human's decision. This is the same shape a production webhook handler receiving a Slack interaction payload, or any other external callback, would take:

```python
webhook_app = FastAPI()


class WebhookDecision(BaseModel):
    accepted: bool
    comment: str | None = None


@webhook_app.post("/resolve/{order_id}")
async def resolve_webhook(order_id: str, decision: WebhookDecision) -> dict:
    future = _pending.pop(order_id, None)
    if future is not None and not future.done():
        default_comment = (
            "approved via webhook" if decision.accepted else "rejected via webhook"
        )
        future.set_result(
            Verdict(
                accepted=decision.accepted, comment=decision.comment or default_comment
            )
        )
    return {"resolved": future is not None}
```

!!! note "The route must be `async def`"
    Defining the route as `async def` keeps it on the same event loop as the pending future, so resolving it is a plain `future.set_result(...)`. A sync route runs in FastAPI's thread pool instead, which would need cross-thread signaling to resolve a future safely.

## Gating the node

With the backend defined, attaching it is the same as any other `pre_verifier`:

```python
@rt.function_node(middleware=[hil_gate])
def refund(order_id: str, amount: float) -> str:
    return f"refunded {amount} for {order_id}"


refund_flow = rt.Flow(name="webhook_refund_flow", entry_point=refund)
```

Running the flow starts the FastAPI server and the Streamlit approval page alongside it, then awaits `refund_flow.ainvoke(...)` until the webhook route resolves the pending future -- approved, rejected, or timed out.

## Generalizing beyond Streamlit

Streamlit here is only a stand-in for a human clicking a button somewhere. The pattern -- register a `Future`, suspend on it in `approve_fn`, resolve it from an independent handler -- applies unchanged to a real Slack app, an internal admin panel, or any other system that can make an HTTP call back into your service once a person acts.
