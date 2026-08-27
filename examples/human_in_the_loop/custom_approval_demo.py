"""HIL backend: "custom" isn't a backend to build -- it's already free.

`pre_verifier` accepts any callable matching `Callable[P, Verdict]` (or
returning an awaitable of one). There's nothing HIL-specific to add for a
"custom" backend beyond documenting that any business logic -- a policy check,
a call to an internal risk service, a lookup in a spreadsheet -- can be an
`approve_fn` as-is.

The more interesting demo is composing backends: cheap/automatic checks first,
escalating to a human only when needed. This one auto-approves small refunds
and only escalates above a threshold. By default that escalation blocks on a
real terminal prompt -- an actual human, actually interrupted, via `input()`
in a worker thread so it doesn't stall the event loop. Pass `--fake` to swap
in a scripted stand-in instead (no prompt, useful for unattended runs).

Run: uv run python examples/human_in_the_loop/custom_approval_demo.py
     uv run python examples/human_in_the_loop/custom_approval_demo.py --fake
"""

import argparse
import asyncio

import railtracks as rt
from railtracks.middleware import Verdict, VerifierRejectedError
from railtracks.prebuilt.middleware import pre_verifier

AUTO_APPROVE_LIMIT = 50.0

##### Two interchangeable "human" backends: swapped via --fake #####


async def real_human_review(order_id: str, amount: float) -> Verdict:
    """Block on an actual terminal prompt -- a real human, really interrupted."""
    prompt = (
        f"\nEscalated: approve refund of {amount} for order {order_id}? [y/N/comment]: "
    )
    reply = (await asyncio.to_thread(input, prompt)).strip()
    if reply.lower() in ("y", "yes"):
        return Verdict(accepted=True)
    if reply.lower() in ("", "n", "no"):
        return Verdict(accepted=False)
    return Verdict(accepted=False, comment=reply)  # anything else: decline-with-comment


async def fake_human_review(order_id: str, amount: float) -> Verdict:
    """Scripted stand-in for a human -- no prompt, for unattended (--fake) runs."""
    print(f"Escalating refund of {amount} for order {order_id} to a (fake) human...")
    await asyncio.sleep(0.1)  # standing in for real latency
    return Verdict(accepted=amount <= 500, comment="reviewed by fake_human_review")


_human_review = real_human_review  # rebound to fake_human_review by --fake in main()

##### The custom, policy-driven HIL backend #####


async def policy_then_escalate(order_id: str, amount: float) -> Verdict:
    if amount <= AUTO_APPROVE_LIMIT:
        return Verdict(accepted=True, comment="auto-approved: under policy limit")
    return await _human_review(order_id, amount)


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

    # Over the limit: escalates to a human (real prompt, or --fake for scripted).
    print(await refund_flow.ainvoke(order_id="A2", amount=300.0))

    # Also over the limit -- try declining this one to see the propagated error.
    try:
        print(await refund_flow.ainvoke(order_id="A3", amount=900.0))
    except VerifierRejectedError as e:
        print(f"Refund declined: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fake",
        action="store_true",
        help="Use a scripted stand-in reviewer instead of a real terminal prompt.",
    )
    args = parser.parse_args()
    if args.fake:
        _human_review = fake_human_review

    asyncio.run(main())
