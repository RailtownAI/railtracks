"""HIL backend: "custom" isn't a backend to build -- it's already free.

`pre_verifier` accepts any callable matching `Callable[P, Verdict]` (or
returning an awaitable of one). There's nothing HIL-specific to add for a
"custom" backend beyond documenting that any business logic -- a policy check,
a call to an internal risk service, a lookup in a spreadsheet -- can be an
`approve_fn` as-is.

The more interesting demo is composing backends: cheap/automatic checks first,
escalating to a human only when needed. This one auto-approves small refunds
and only escalates to a (fake, in-memory) human backend above a threshold.

Run: uv run python examples/human_in_the_loop/custom_approval_demo.py
"""

import asyncio

import railtracks as rt
from railtracks.middleware import Verdict, VerifierRejectedError
from railtracks.prebuilt.middleware import pre_verifier

AUTO_APPROVE_LIMIT = 50.0

##### A fake "human" backend, standing in for any real one #####
# (e.g. the webhook backend from the other demo in this folder -- this one
# just hardcodes a decision to keep the demo self-contained.)


async def fake_human_review(order_id: str, amount: float) -> Verdict:
    print(f"Escalating refund of {amount} for order {order_id} to a human...")
    await asyncio.sleep(0.1)  # standing in for real latency
    return Verdict(accepted=amount <= 500, comment="reviewed by fake_human_review")


##### The custom, policy-driven HIL backend #####


async def policy_then_escalate(order_id: str, amount: float) -> Verdict:
    if amount <= AUTO_APPROVE_LIMIT:
        return Verdict(accepted=True, comment="auto-approved: under policy limit")
    return await fake_human_review(order_id, amount)


hil_gate = pre_verifier(policy_then_escalate, name="custom_hil")

##### Agent / tool gated by the HIL backend #####


@rt.function_node(middleware=[hil_gate])
def refund(order_id: str, amount: float) -> str:
    """Refund an order.

    Args:
        order_id (str): The order to refund.
        amount (float): The amount to refund.
    """
    return f"refunded {amount} for {order_id}"


refund_flow = rt.Flow(name="custom_refund_flow", entry_point=refund)


async def main():
    # Under the limit: auto-approved, no escalation.
    print(await refund_flow.ainvoke(order_id="A1", amount=20.0))

    # Over the limit: escalates, and the fake reviewer approves it.
    print(await refund_flow.ainvoke(order_id="A2", amount=300.0))

    # Over the limit and over what the fake reviewer will accept.
    try:
        print(await refund_flow.ainvoke(order_id="A3", amount=900.0))
    except VerifierRejectedError as e:
        print(f"Refund declined: {e}")


if __name__ == "__main__":
    asyncio.run(main())
