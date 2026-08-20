"""Unit and end-to-end tests for the general verifier middleware (#1266).

A verifier is an ordinary `wrap_node` middleware: it runs an approve callable
against the node's own `*args, **kwargs` before deciding whether to forward
the call onward. Decline == don't call `call(...)`, raise instead.
"""

import asyncio

import pytest
import railtracks as rt
from railtracks.verifiers import Verdict, VerifierRejectedError, verifier


class TestVerifierUnit:
    async def test_accept_forwards_the_call_unchanged(self):
        gate = verifier(lambda *a, **k: Verdict(accepted=True))

        async def core(x):
            return x * 2

        assert await gate.wrap(core)(5) == 10

    async def test_decline_raises_and_never_calls_core(self):
        gate = verifier(lambda *a, **k: Verdict(accepted=False))

        async def core():
            raise AssertionError("core should not run")

        with pytest.raises(VerifierRejectedError):
            await gate.wrap(core)()

    async def test_decline_with_comment_is_carried_into_the_exception(self):
        gate = verifier(lambda *a, **k: Verdict(accepted=False, comment="too risky"))

        async def core():
            raise AssertionError("core should not run")

        with pytest.raises(VerifierRejectedError, match="too risky"):
            await gate.wrap(core)()

    async def test_accept_with_comments_rewrites_args(self):
        gate = verifier(
            lambda *a, **k: Verdict(accepted=True, comment="lowered", args=(1,))
        )

        async def core(x):
            return x

        assert await gate.wrap(core)(100) == 1

    async def test_accept_with_comments_rewrites_kwargs(self):
        gate = verifier(lambda *a, **k: Verdict(accepted=True, kwargs={"amount": 1}))

        async def core(amount):
            return amount

        assert await gate.wrap(core)(amount=100) == 1

    async def test_approve_fn_receives_the_nodes_own_args_and_kwargs(self):
        seen = {}

        def approve(order_id, amount):
            seen["order_id"] = order_id
            seen["amount"] = amount
            return Verdict(accepted=True)

        gate = verifier(approve)

        async def core(order_id, amount):
            return f"{order_id}:{amount}"

        assert await gate.wrap(core)(order_id="A1", amount=5) == "A1:5"
        assert seen == {"order_id": "A1", "amount": 5}

    async def test_async_approve_fn_is_supported(self):
        async def approve(*a, **k):
            return Verdict(accepted=True)

        gate = verifier(approve)

        async def core(x):
            return x

        assert await gate.wrap(core)(7) == 7

    async def test_timeout_rejects_with_reason_timeout(self):
        async def approve(*a, **k):
            await asyncio.sleep(10)
            return Verdict(accepted=True)

        gate = verifier(approve, timeout=0.01)

        async def core():
            raise AssertionError("core should not run")

        with pytest.raises(VerifierRejectedError, match="timeout"):
            await gate.wrap(core)()

    def test_bare_decorator_form(self):
        @verifier
        async def approve(*a, **k):
            return Verdict(accepted=True)

        assert isinstance(approve, rt.middleware.Middleware)

    def test_called_decorator_form_with_options(self):
        @verifier(timeout=5, name="my_gate")
        def approve(*a, **k):
            return Verdict(accepted=True)

        assert approve.name == "my_gate"


class TestVerifierEndToEnd:
    """Proves the verifier holds through the real execution path: rt.call ->
    Task.invoke -> node.wrapped_invoke -> middleware.run(invoke)."""

    def test_approved_call_runs_the_node(self):
        gate = verifier(lambda order_id, amount: Verdict(accepted=amount <= 100))

        @rt.function_node(middleware=[gate])
        def refund(order_id: str, amount: float) -> str:
            """Refund an order."""
            return f"refunded {amount} for {order_id}"

        async def top_level():
            with rt.Session():
                return await rt.call(refund, order_id="A1", amount=50)

        assert asyncio.run(top_level()) == "refunded 50 for A1"

    def test_declined_call_blocks_the_node_and_propagates(self):
        gate = verifier(lambda order_id, amount: Verdict(accepted=amount <= 100))
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
        assert ran["value"] is False
