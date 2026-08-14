"""Verifier playground — hands-on intro for the real `rt.verifier` middleware (#1266).

This supersedes the naive `hil_gate` prototype in `middleware_playground.py`, which
was written before the real verifier landed. `rt.verifier` is the shipped API:

    verifier(approve_fn, *, timeout=None, name=None) -> Middleware

`approve_fn` is called with the SAME `*args, **kwargs` the wrapped node was called
with (sync or async, both supported) and must return a `Verdict`:
    - accept:               Verdict(accepted=True)
    - accept with comments: Verdict(accepted=True, comment=..., args=..., kwargs=...)
                            (args/kwargs override what gets forwarded to the node)
    - decline:              Verdict(accepted=False)
    - decline with comments: Verdict(accepted=False, comment=...)

On decline, `VerifierRejectedError` is raised (message = the verdict's comment, or
"timeout" on timeout, or "rejected" if no comment was given) and the node's own body
never runs. See `packages/railtracks/src/railtracks/middleware/verifier.py` for the
implementation and `packages/railtracks/tests/unit_tests/middlewares/test_verifier.py`
for the full test suite this demo is consistent with.

Uses NO network/LLM calls and NO interactive `input()` — everything is deterministic
so it runs offline and can be executed standalone:

    python examples/verifier_playground.py
"""

import asyncio

import railtracks as rt
from railtracks.middleware import Verdict, VerifierRejectedError, verifier

# ---------------------------------------------------------------------------
# A single plain tool, reused across every demo below. `ran_count` lets us
# prove a declined call never actually executes the node body.
# ---------------------------------------------------------------------------

ran_count = {"value": 0}


@rt.function_node
def refund_customer(order_id: str, amount: float) -> str:
    """Issue a refund for an order.

    Args:
        order_id: The id of the order to refund.
        amount: The dollar amount to refund.
    """
    ran_count["value"] += 1
    return f"Refunded ${amount:.2f} for order {order_id}"


# ---------------------------------------------------------------------------
# 1. Plain accept: the approve_fn always accepts, so the call goes through
#    completely unchanged.
# ---------------------------------------------------------------------------


async def demo_accept():
    print("\n=== demo: plain accept ===")

    always_accept = verifier(lambda *a, **k: Verdict(accepted=True))
    guarded_refund = rt.couple(refund_customer, middleware=[always_accept])

    with rt.Session():
        result = await rt.call(guarded_refund, order_id="A100", amount=50)
        print("result:", result)


# ---------------------------------------------------------------------------
# 2. Decline: reject any refund over $100. A small amount goes through; a
#    large one raises VerifierRejectedError and the node body never runs.
# ---------------------------------------------------------------------------


def approve_small_refunds(order_id: str, amount: float) -> Verdict:
    if amount > 100:
        return Verdict(accepted=False, comment="amount too high")
    return Verdict(accepted=True)


async def demo_decline():
    print("\n=== demo: decline ===")

    gate = verifier(approve_small_refunds)
    guarded_refund = rt.couple(refund_customer, middleware=[gate])

    before = ran_count["value"]
    with rt.Session():
        result = await rt.call(guarded_refund, order_id="A200", amount=50)
        print("small amount approved, result:", result)
        assert ran_count["value"] == before + 1

    with rt.Session():
        try:
            await rt.call(guarded_refund, order_id="A201", amount=500)
        except VerifierRejectedError as e:
            print(f"large amount correctly rejected: {e}")
        assert ran_count["value"] == before + 1, "node body ran on a declined call!"
        print("confirmed: node body did not run for the rejected call")


# ---------------------------------------------------------------------------
# 3. Accept with comments, rewriting kwargs: approve but cap the amount that
#    actually gets forwarded to the node.
# ---------------------------------------------------------------------------


def approve_and_cap(order_id: str, amount: float) -> Verdict:
    capped = min(amount, 100)
    return Verdict(
        accepted=True,
        comment=f"capped {amount} -> {capped}",
        kwargs={"order_id": order_id, "amount": capped},
    )


async def demo_accept_with_override():
    print("\n=== demo: accept with comments, overriding kwargs ===")

    gate = verifier(approve_and_cap)
    guarded_refund = rt.couple(refund_customer, middleware=[gate])

    with rt.Session():
        result = await rt.call(guarded_refund, order_id="A300", amount=999)
        print("result (should reflect the capped $100, not $999):", result)


# ---------------------------------------------------------------------------
# 4. Timeout: an async approve_fn that sleeps longer than `timeout=` is
#    treated as declined with reason "timeout".
# ---------------------------------------------------------------------------


async def slow_approve(order_id: str, amount: float) -> Verdict:
    await asyncio.sleep(5)
    return Verdict(accepted=True)


async def demo_timeout():
    print("\n=== demo: timeout ===")

    gate = verifier(slow_approve, timeout=0.05)
    guarded_refund = rt.couple(refund_customer, middleware=[gate])

    with rt.Session():
        try:
            await rt.call(guarded_refund, order_id="A400", amount=25)
        except VerifierRejectedError as e:
            print(f"call correctly rejected on timeout: {e}")


# ---------------------------------------------------------------------------
# 5. (nice-to-have) sync vs async approve_fn — both work identically.
# ---------------------------------------------------------------------------


def sync_approve(order_id: str, amount: float) -> Verdict:
    return Verdict(accepted=True)


async def async_approve(order_id: str, amount: float) -> Verdict:
    return Verdict(accepted=True)


async def demo_sync_vs_async():
    print("\n=== demo: sync vs async approve_fn ===")

    sync_guarded = rt.couple(refund_customer, middleware=[verifier(sync_approve)])
    async_guarded = rt.couple(refund_customer, middleware=[verifier(async_approve)])

    with rt.Session():
        sync_result = await rt.call(sync_guarded, order_id="A500", amount=10)
        async_result = await rt.call(async_guarded, order_id="A501", amount=10)
        print("sync approve_fn result:", sync_result)
        print("async approve_fn result:", async_result)


async def main():
    await demo_accept()
    await demo_decline()
    await demo_accept_with_override()
    await demo_timeout()
    await demo_sync_vs_async()


if __name__ == "__main__":
    asyncio.run(main())
