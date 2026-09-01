# Human-in-the-Loop: LLM Reviewers

The [Verifiers](../../documentation/agent_design/middleware/verifiers/overview.md) overview covers `pre_verifier`/`post_verifier` mechanics with a fixed threshold as `approve_fn`. In production, the reviewer is more often a second agent applying a written policy -- auto-handling the common case, with a human only ever entering the loop for what the policy can't resolve. This walkthrough builds that shape: a refund flow with an LLM reviewing both the request going in and the reply going out.

The full runnable file is [`examples/human_in_the_loop/llm_approval_demo.py`](https://github.com/RailtownAI/railtracks/blob/main/examples/human_in_the_loop/llm_approval_demo.py). It makes real LLM calls, so set `OPENAI_API_KEY` (or swap the model) before running it:

```bash
uv run python examples/human_in_the_loop/llm_approval_demo.py
```

The excerpts below are abridged for readability; imports and the `main()` runner are omitted. See the file linked above for the complete, runnable version.

## Pre-check: policy before the refund is processed

The reviewer is an ordinary agent with a structured output schema. Its verdict becomes the `Verdict` the verifier needs:

```python
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
    return f"refunded {amount} for {order_id}"
```

`approve_fn` can be `async` -- it runs an entire `rt.call` to another agent before returning a verdict, which is exactly the "compose a cheap check with an escalation" pattern from the overview, just with an LLM instead of a fixed threshold.

## Post-check: compliance review of a drafted reply

The same idea applies after a node runs. Here a second agent reviews a drafted customer reply and, if it promises a specific dollar amount, rewrites it via `Verdict(result=...)`:

```python
class ComplianceReview(BaseModel):
    accepted: bool
    comment: str
    revised_reply: str | None = None


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
    resp = await rt.call(reply_drafter, customer_message)
    return resp.content
```

`review.revised_reply` is `None` when the draft needed no changes -- and `Verdict.result` propagates the original result whenever the override is `None`, so leaving it unset is the correct way for the reviewer to say "no change needed."

## Both on one node

Nothing new is required to gate the same node on both ends -- attach both middleware, in the order you want them evaluated:

```python
@rt.function_node(
    middleware=[
        pre_verifier(llm_policy_check, name="llm_policy_pre"),
        post_verifier(confirm_review, name="confirm_review_post"),
    ]
)
def refund_with_both(order_id: str, amount: float, note: str) -> str:
    return f"refunded {amount} for {order_id}"
```

## Escalating to an actual human

An LLM reviewer doesn't have to be the final word. [`custom_approval_demo.py`](https://github.com/RailtownAI/railtracks/blob/main/examples/human_in_the_loop/custom_approval_demo.py) shows the same composition idea in the other direction: auto-approve under a threshold, escalate to a real terminal prompt above it. Since `approve_fn` is just a callable, nothing stops you from combining both -- auto-approve, then LLM-review, then escalate to a human only when the LLM itself is unsure.
