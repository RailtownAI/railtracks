"""HIL backend: webhook-style external resolution.

Register a pending approval, then suspend the coroutine on an `asyncio.Future`
until something *outside* it -- in real life, a Slack button click or a UI
callback hitting a webhook route -- resolves that future by id. This script
fakes the "outside" half with a background task that sleeps briefly and then
calls `resolve_approval(...)` directly, standing in for what a webhook
handler would do on a real request.

Run: uv run python examples/human_in_the_loop/webhook_approval_demo.py
"""

import asyncio

import railtracks as rt
from railtracks.middleware import Verdict, VerifierRejectedError
from railtracks.prebuilt.middleware import pre_verifier

##### The HIL backend #####

_pending: dict[str, asyncio.Future] = {}


def resolve_approval(approval_id: str, verdict: Verdict) -> None:
    """Called by whatever receives the external event (a webhook route, a
    Slack interaction handler, ...) to deliver the human's decision."""
    future = _pending.pop(approval_id, None)
    if future is not None and not future.done():
        future.set_result(verdict)


async def ask_via_webhook(order_id: str, amount: float) -> Verdict:
    """Register a pending approval and wait for it to be resolved externally."""
    approval_id = order_id
    future: asyncio.Future = asyncio.get_running_loop().create_future()
    _pending[approval_id] = future

    print(
        f"Waiting for external approval of refund {amount} for order "
        f"{order_id} (approval_id={approval_id})..."
    )
    return await future


hil_gate = pre_verifier(ask_via_webhook, timeout=30, name="webhook_hil")

##### Agent / tool gated by the HIL backend #####


@rt.function_node(middleware=[hil_gate])
def refund(order_id: str, amount: float) -> str:
    """Refund an order.

    Args:
        order_id (str): The order to refund.
        amount (float): The amount to refund.
    """
    return f"refunded {amount} for {order_id}"


async def simulate_webhook_callback(order_id: str, delay: float = 2.0) -> None:
    """Stand-in for a real webhook: a human clicks 'approve' in Slack/a UI
    some time later, and that request handler resolves the pending future."""
    await asyncio.sleep(delay)
    print(f"(simulated) webhook received: approving order {order_id}")
    resolve_approval(order_id, Verdict(accepted=True, comment="approved via Slack"))


refund_flow = rt.Flow(name="webhook_refund_flow", entry_point=refund)


async def main():
    asyncio.create_task(simulate_webhook_callback("A1"))
    try:
        result = await refund_flow.ainvoke(order_id="A1", amount=42.50)
        print(result)
    except VerifierRejectedError as e:
        print(f"Refund declined: {e}")


if __name__ == "__main__":
    asyncio.run(main())
