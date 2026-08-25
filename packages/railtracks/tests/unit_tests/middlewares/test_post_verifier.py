"""Unit and end-to-end tests for the post-call verifier middleware (#1485).

A post_verifier is an ordinary `wrap_node` middleware, modeled on `after_node`:
it runs the wrapped call first, then runs an approve callable against the
node's own `*args, **kwargs` plus the produced `result`, before deciding
whether/how that result propagates onward. Unlike `pre_verifier`, decline
cannot undo the call -- the node's body has already run by the time
`approve_fn` sees anything -- it only stops the result from propagating
further.
"""

import asyncio

import pytest
import railtracks as rt
from railtracks.middleware import Verdict, VerifierRejectedError
from railtracks.prebuilt.middleware import post_verifier


class TestPostVerifierUnit:
    async def test_accept_forwards_the_result_unchanged(self):
        gate = post_verifier(lambda *a, result, **k: Verdict(accepted=True))

        async def core(x):
            return x * 2

        assert await gate.wrap(core)(5) == 10

    async def test_decline_raises_but_core_already_ran(self):
        ran = {"value": False}

        async def core():
            ran["value"] = True
            return "done"

        gate = post_verifier(lambda *a, result, **k: Verdict(accepted=False))

        with pytest.raises(VerifierRejectedError):
            await gate.wrap(core)()
        assert ran["value"] is True

    async def test_decline_with_comment_is_carried_into_the_exception(self):
        gate = post_verifier(
            lambda *a, result, **k: Verdict(accepted=False, comment="too risky")
        )

        async def core():
            return "done"

        with pytest.raises(VerifierRejectedError, match="too risky"):
            await gate.wrap(core)()

    async def test_accept_with_result_override_replaces_the_propagated_value(self):
        gate = post_verifier(
            lambda *a, result, **k: Verdict(
                accepted=True, comment="redacted", result="scrubbed"
            )
        )

        async def core(x):
            return "raw"

        assert await gate.wrap(core)(1) == "scrubbed"

    async def test_accept_without_result_override_passes_the_original_through(self):
        gate = post_verifier(lambda *a, result, **k: Verdict(accepted=True))

        async def core(x):
            return "raw"

        assert await gate.wrap(core)(1) == "raw"

    async def test_approve_fn_receives_the_nodes_own_args_kwargs_and_result(self):
        seen = {}

        def approve(order_id, amount, result):
            seen["order_id"] = order_id
            seen["amount"] = amount
            seen["result"] = result
            return Verdict(accepted=True)

        gate = post_verifier(approve)

        async def core(order_id, amount):
            return f"{order_id}:{amount}"

        assert (
            await gate.wrap(core)(order_id="A1", amount=5) == "A1:5"
        )
        assert seen == {"order_id": "A1", "amount": 5, "result": "A1:5"}

    async def test_async_approve_fn_is_supported(self):
        async def approve(*a, result, **k):
            return Verdict(accepted=True)

        gate = post_verifier(approve)

        async def core(x):
            return x

        assert await gate.wrap(core)(7) == 7

    async def test_timeout_rejects_with_reason_timeout(self):
        async def approve(*a, result, **k):
            await asyncio.sleep(10)
            return Verdict(accepted=True)

        gate = post_verifier(approve, timeout=0.01)

        async def core():
            return "done"

        with pytest.raises(VerifierRejectedError, match="timeout"):
            await gate.wrap(core)()

    def test_bare_decorator_form(self):
        @post_verifier
        async def approve(*a, result, **k):
            return Verdict(accepted=True)

        assert isinstance(approve, rt.middleware.Middleware)

    def test_called_decorator_form_with_options(self):
        @post_verifier(timeout=5, name="my_gate")
        def approve(*a, result, **k):
            return Verdict(accepted=True)

        assert approve.name == "my_gate"


class TestPostVerifierEndToEnd:
    """Proves the post_verifier holds through the real execution path: rt.call ->
    Task.invoke -> node.wrapped_invoke -> middleware.run(invoke)."""

    def test_approved_call_propagates_the_result(self):
        gate = post_verifier(lambda order_id, amount, result: Verdict(accepted=True))

        @rt.function_node(middleware=[gate])
        def refund(order_id: str, amount: float) -> str:
            """Refund an order."""
            return f"refunded {amount} for {order_id}"

        async def top_level():
            with rt.Session():
                return await rt.call(refund, order_id="A1", amount=50)

        assert asyncio.run(top_level()) == "refunded 50 for A1"

    def test_accepted_with_override_propagates_the_overridden_result(self):
        gate = post_verifier(
            lambda order_id, amount, result: Verdict(accepted=True, result="redacted")
        )

        @rt.function_node(middleware=[gate])
        def refund(order_id: str, amount: float) -> str:
            """Refund an order."""
            return f"refunded {amount} for {order_id}"

        async def top_level():
            with rt.Session():
                return await rt.call(refund, order_id="A1", amount=50)

        assert asyncio.run(top_level()) == "redacted"

    def test_declined_call_still_ran_the_node_but_blocks_propagation(self):
        gate = post_verifier(
            lambda order_id, amount, result: Verdict(accepted=amount <= 100)
        )
        ran = {"value": False}

        @rt.function_node(middleware=[gate])
        def refund(order_id: str, amount: float) -> str:
            """Refund an order."""
            ran["value"] = True
            return f"refunded {amount} for {order_id}"

        async def top_level():
            with rt.Session():
                return await rt.call(refund, order_id="A1", amount=500)

        with pytest.raises(VerifierRejectedError):
            asyncio.run(top_level())
        assert ran["value"] is True


class TestVerifierComposition:
    """Proves pre_verifier and post_verifier compose in a single middleware=[]
    list with zero new chain plumbing (MiddlewareChain.run already handles
    ordering -- see railtracks/middleware/chain.py)."""

    def test_pre_and_post_both_apply_on_one_node(self):
        from railtracks.prebuilt.middleware import pre_verifier

        pre_seen = {"value": False}
        post_seen = {"value": False}

        def approve_draft(to, subject, body):
            pre_seen["value"] = True
            return Verdict(accepted=True)

        def confirm_sent(to, subject, body, result):
            post_seen["value"] = True
            return Verdict(accepted=True)

        @rt.function_node(
            middleware=[
                pre_verifier(approve_draft, name="approve_email"),
                post_verifier(confirm_sent, name="confirm_email"),
            ]
        )
        def send_email(to: str, subject: str, body: str) -> str:
            """Send an email."""
            return f"sent to {to}: {subject}"

        async def top_level():
            with rt.Session():
                return await rt.call(
                    send_email, to="a@b.com", subject="hi", body="hello"
                )

        result = asyncio.run(top_level())
        assert result == "sent to a@b.com: hi"
        assert pre_seen["value"] is True
        assert post_seen["value"] is True

    def test_post_placed_outside_retry_only_sees_the_final_settled_result(self):
        from railtracks.prebuilt.middleware import Retry

        attempts = {"count": 0}
        reviewed_results = []

        def always_accept(order_id, amount, result):
            reviewed_results.append(result)
            return Verdict(accepted=True)

        @rt.function_node(
            middleware=[
                post_verifier(always_accept),
                Retry(max_tries=3, retry_on=(ValueError,)),
            ]
        )
        def flaky_refund(order_id: str, amount: float) -> str:
            """Refund an order via a flaky downstream payment API."""
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise ValueError("downstream hiccup")
            return f"refunded {amount} for {order_id}"

        async def top_level():
            with rt.Session():
                return await rt.call(flaky_refund, order_id="A1", amount=50)

        assert asyncio.run(top_level()) == "refunded 50 for A1"
        assert attempts["count"] == 3
        assert reviewed_results == ["refunded 50 for A1"]
