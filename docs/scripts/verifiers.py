"""Runnable examples for the verifiers docs.

Snippet regions (--8<-- [start:name]) are pulled into the verifiers
overview page by MkDocs. Type-checked in CI via scripts/docs_validation.sh.
Kept local/synchronous -- no API keys or servers required to read the docs.
"""

from __future__ import annotations

# --8<-- [start: pre_verifier_basic]
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
# --8<-- [end: pre_verifier_basic]


# --8<-- [start: post_verifier_basic]
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
# --8<-- [end: post_verifier_basic]


# --8<-- [start: composed]
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
# --8<-- [end: composed]
