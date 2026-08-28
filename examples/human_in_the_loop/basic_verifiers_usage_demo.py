"""Local demo of #1485's pre_verifier / post_verifier.

Not part of the PR -- untracked, for poking around locally only.

- pre_verifier gates a call BEFORE it runs: decline and the node's body
  never executes.
- post_verifier gates a call's OUTPUT AFTER it has already run: its approve
  function takes the produced `result` as its FIRST argument, then the
  node's own args. Decline can't undo the call, only stop the result from
  propagating; accept can optionally rewrite what propagates via
  Verdict(result=...).

Run: uv run python examples/human_in_the_loop/basic_verifiers_usage_demo.py
"""

import railtracks as rt
from railtracks.middleware import Verdict, VerifierRejectedError
from railtracks.prebuilt.middleware import post_verifier, pre_verifier

##### 1. Pre-only: gate whether the call happens at all #####


def approve_refund(order_id: str, amount: float) -> Verdict:
    ok = amount <= 100
    return Verdict(accepted=ok, comment=None if ok else "over the auto-approve limit")


@rt.function_node(middleware=[pre_verifier(approve_refund)])
def refund(order_id: str, amount: float) -> str:
    """Refund an order."""
    return f"refunded {amount} for {order_id}"


refund_flow = rt.Flow(name="pre_verifier demo", entry_point=refund)


##### 2. Post-only: gate whether/how the call's OUTPUT propagates #####


def redact_ssn(result: dict, query: str) -> Verdict[dict]:
    scrubbed = {k: v for k, v in result.items() if k != "ssn"}
    return Verdict(accepted=True, comment="redacted SSN", result=scrubbed)


@rt.function_node(middleware=[post_verifier(redact_ssn)])
def lookup_customer(query: str) -> dict:
    """Look up a customer record."""
    return {"name": "Jane Doe", "ssn": "000-00-0000", "query": query}


lookup_flow = rt.Flow(name="post_verifier demo", entry_point=lookup_customer)


##### 3. Both on one node: approve the request, then check what came out #####


def approve_request(order_id: str, amount: float) -> Verdict:
    return Verdict(accepted=True, comment="looks fine")


def confirm_result(result: str, order_id: str, amount: float) -> Verdict:
    print(f"  [confirm_result saw]: {result!r}")
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


if __name__ == "__main__":
    print("--- pre_verifier: approved (amount <= 100) ---")
    print(refund_flow.invoke(order_id="A1", amount=50))

    print("\n--- pre_verifier: declined (amount > 100), node never ran ---")
    try:
        refund_flow.invoke(order_id="A2", amount=500)
    except VerifierRejectedError as e:
        print(f"declined: {e}")

    print("\n--- post_verifier: SSN redacted after the call already ran ---")
    print(lookup_flow.invoke(query="Jane Doe"))

    print("\n--- pre_verifier + post_verifier on one node ---")
    print(both_flow.invoke(order_id="A3", amount=25))
