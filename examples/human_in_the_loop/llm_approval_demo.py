"""HIL backend: an LLM as the reviewer -- pre, post, and both.

The realest use case for `pre_verifier`/`post_verifier`: neither a human at a
terminal nor a fixed threshold, but an LLM applying a written policy. This is
the shape most production guardrails actually take -- auto-handle the common
case, and (as `custom_approval_demo.py` shows) it's trivial to escalate to a
real human only when the LLM itself is unsure.

- Pre: a refund is checked against store policy *before* it's processed --
  large refunds need a documented reason in the order note.
- Post: a customer-support reply is drafted by one agent, then reviewed for
  policy violations (and redacted if needed) by a second, *after* it's
  already been generated.
- Both: a refund is policy-checked going in, and its confirmation message is
  reviewed coming out.

Each `approve_fn` is a real LLM call: set OPENAI_API_KEY before running (or
swap the model below for another provider).

Run: uv run python examples/human_in_the_loop/llm_approval_demo.py
"""

import asyncio

import railtracks as rt
from pydantic import BaseModel
from railtracks.middleware import Verdict, VerifierRejectedError
from railtracks.prebuilt.middleware import post_verifier, pre_verifier

##### 1. Pre-only: an LLM policy check before the refund is processed #####


class PolicyReview(BaseModel):
    accepted: bool
    comment: str


policy_reviewer = rt.agent_node(
    name="RefundPolicyReviewer",
    system_message=(
        "You enforce refund policy: refunds over $200 require a documented "
        "reason in the order note. Anything else is fine. Given a refund "
        "request, decide whether to accept it and give a one-sentence reason."
    ),
    llm=rt.llm.OpenAILLM("gpt-4o-mini"),
    output_schema=PolicyReview,
)


async def llm_policy_check(order_id: str, amount: float, note: str) -> Verdict:
    resp = await rt.call(
        policy_reviewer,
        f"Refund request: order_id={order_id!r}, amount={amount}, note={note!r}",
    )
    review = resp.structured
    return Verdict(accepted=review.accepted, comment=review.comment)


@rt.function_node(middleware=[pre_verifier(llm_policy_check, name="llm_policy_pre")])
def refund(order_id: str, amount: float, note: str) -> str:
    """Refund an order."""
    return f"refunded {amount} for {order_id}"


refund_flow = rt.Flow(name="llm_pre_refund_flow", entry_point=refund)


##### 2. Post-only: an LLM reviews a drafted reply before it goes out #####


class ComplianceReview(BaseModel):
    accepted: bool
    comment: str
    revised_reply: str | None = None
    """If the reply needed changes, the corrected version."""


reply_drafter = rt.agent_node(
    name="SupportReplyDrafter",
    system_message=(
        "Draft a short, friendly reply to the customer's message. If they "
        "ask for money back, agree and confirm the exact dollar amount "
        "they'll be refunded."
    ),
    llm=rt.llm.OpenAILLM("gpt-4o-mini"),
)

compliance_reviewer = rt.agent_node(
    name="ComplianceReviewer",
    system_message=(
        "You review draft customer-support replies before they're sent. "
        "Always accept, but if the draft promises a specific refund amount "
        "or discount, set revised_reply to a rewritten version that says a "
        "specialist will follow up instead, with no dollar amount. If the "
        "draft is already fine, leave revised_reply unset."
    ),
    llm=rt.llm.OpenAILLM("gpt-4o-mini"),
    output_schema=ComplianceReview,
)


async def llm_compliance_check(result: str, customer_message: str) -> Verdict[str]:
    resp = await rt.call(compliance_reviewer, f"Draft reply: {result!r}")
    review = resp.structured
    return Verdict(
        accepted=review.accepted,
        comment=review.comment,
        result=review.revised_reply,
    )


@rt.function_node(
    middleware=[post_verifier(llm_compliance_check, name="llm_compliance_post")]
)
async def draft_reply(customer_message: str) -> str:
    """Draft a reply to a customer's support message."""
    resp = await rt.call(reply_drafter, customer_message)
    return resp.content


draft_reply_flow = rt.Flow(name="llm_post_reply_flow", entry_point=draft_reply)


##### 3. Both on one node: policy-check the request, then review the output ####


async def confirm_review(
    result: str, order_id: str, amount: float, note: str
) -> Verdict:
    print(f"  [confirm_review saw]: {result!r}")
    return Verdict(accepted=True)


@rt.function_node(
    middleware=[
        pre_verifier(llm_policy_check, name="llm_policy_pre"),
        post_verifier(confirm_review, name="confirm_review_post"),
    ]
)
def refund_with_both(order_id: str, amount: float, note: str) -> str:
    """Refund an order, policy-checked going in and reviewed coming out."""
    return f"refunded {amount} for {order_id}"


both_flow = rt.Flow(name="llm_pre_post_refund_flow", entry_point=refund_with_both)


async def main():
    print("--- pre_verifier: LLM accepts (small refund, no policy concern) ---")
    print(await refund_flow.ainvoke(order_id="A1", amount=50, note="damaged item"))

    print("\n--- pre_verifier: LLM declines (large refund, no documented reason) ---")
    try:
        await refund_flow.ainvoke(order_id="A2", amount=500, note="customer asked")
    except VerifierRejectedError as e:
        print(f"declined: {e}")

    print("\n--- post_verifier: LLM rewrites a reply that promised a refund amount ---")
    print(
        await draft_reply_flow.ainvoke(
            customer_message="My order arrived broken, can I get $50 back?"
        )
    )

    print("\n--- pre_verifier + post_verifier on one node ---")
    print(await both_flow.ainvoke(order_id="A3", amount=25, note="wrong size"))


if __name__ == "__main__":
    asyncio.run(main())
