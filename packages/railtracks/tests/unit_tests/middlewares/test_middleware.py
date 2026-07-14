"""Unit tests for the middleware primitive and the MiddlewareChain engine.

Middleware — execution-control wrapper around a callable:
    `async fn(call, *args, **kwargs) -> result`
``call`` is the next callable in the chain; the wrapper is responsible for awaiting it
(or not, to short-circuit).

MiddlewareChain — a flat, ordered list of Middleware. ``run()`` wraps the core callable
with each middleware in ``reversed()`` order, so **index 0 is the outermost layer**: its
"before" code runs first and its "after" code runs last.
"""

import pytest

from railtracks.middleware import Middleware, MiddlewareChain, wrap_node


class TestMiddleware:
    def test_requires_callable(self):
        with pytest.raises(TypeError, match="callable"):
            wrap_node(123)  # type: ignore[arg-type]

    def test_requires_async(self):
        # A sync function is rejected immediately -- middleware must be async.
        with pytest.raises(TypeError, match="async"):
            wrap_node(lambda call, *a, **k: call(*a, **k))  # type: ignore[arg-type]

    def test_decorator_builds_middleware_instance(self):
        @wrap_node
        async def m(call, *args, **kwargs):
            return await call(*args, **kwargs)

        assert isinstance(m, Middleware)

    def test_repr_includes_function_name(self):
        @wrap_node
        async def named_middleware(call, *a, **k):
            return await call(*a, **k)

        assert "named_middleware" in repr(named_middleware)

    async def test_wraps_and_calls(self):
        @wrap_node
        async def double_result(call, *args, **kwargs):
            first = await call(*args, **kwargs)
            return first * 2

        async def core(x):
            return x + 1

        wrapped = double_result.wrap(core)
        assert await wrapped(4) == 10  # (4 + 1) * 2

    async def test_can_short_circuit(self):
        @wrap_node
        async def never(call, *args, **kwargs):
            return "blocked"

        async def core():
            raise AssertionError("core should not run")

        assert await never.wrap(core)() == "blocked"

    async def test_can_transform_args_before_calling(self):
        @wrap_node
        async def upper_args(call, text):
            return await call(text.upper())

        async def core(text):
            return text

        wrapped = upper_args.wrap(core)
        assert await wrapped("hi") == "HI"

    async def test_can_catch_and_translate_exception(self):
        @wrap_node
        async def translate(call, *args, **kwargs):
            try:
                return await call(*args, **kwargs)
            except ValueError as e:
                raise RuntimeError(f"translated: {e}") from e

        async def core():
            raise ValueError("boom")

        with pytest.raises(RuntimeError, match="translated: boom"):
            await translate.wrap(core)()


class TestMiddlewareChain:
    async def test_empty_chain_is_passthrough(self):
        chain = MiddlewareChain()

        async def core(x):
            return x * 2

        assert await chain.run(core, 5) == 10

    async def test_single_middleware_wraps_core(self):
        @wrap_node
        async def add_one_after(call, *args, **kwargs):
            result = await call(*args, **kwargs)
            return result + 1

        chain = MiddlewareChain([add_one_after])

        async def core(x):
            return x * 2

        assert await chain.run(core, 5) == 11  # (5 * 2) + 1

    async def test_index_zero_is_outermost(self):
        """The first entry in the list is the outermost layer: its "before" code runs
        first, and its "after" code (whatever runs after `await call(...)`) runs last."""
        trace = []

        def make(tag):
            @wrap_node
            async def m(call, *args, **kwargs):
                trace.append(f"{tag}-in")
                result = await call(*args, **kwargs)
                trace.append(f"{tag}-out")
                return result

            return m

        chain = MiddlewareChain([make("first"), make("second"), make("third")])

        async def core():
            trace.append("core")
            return "done"

        assert await chain.run(core) == "done"
        assert trace == [
            "first-in",
            "second-in",
            "third-in",
            "core",
            "third-out",
            "second-out",
            "first-out",
        ]

    async def test_middleware_can_short_circuit_the_chain(self):
        @wrap_node
        async def block(call, *args, **kwargs):
            return "blocked"

        chain = MiddlewareChain([block])

        async def core():
            raise AssertionError("core should not run")

        assert await chain.run(core) == "blocked"

    def test_add_middleware_appends(self):
        @wrap_node
        async def m1(call, *a, **k):
            return await call(*a, **k)

        @wrap_node
        async def m2(call, *a, **k):
            return await call(*a, **k)

        chain = MiddlewareChain([m1])
        chain.add_middleware(m2)
        assert chain.middleware == [m1, m2]

    def test_add_middleware_allows_duplicates(self):
        @wrap_node
        async def m(call, *a, **k):
            return await call(*a, **k)

        chain = MiddlewareChain([m])
        chain.add_middleware(m)
        assert chain.middleware == [m, m]

    def test_middleware_property_returns_a_copy(self):
        @wrap_node
        async def m(call, *a, **k):
            return await call(*a, **k)

        chain = MiddlewareChain([m])
        snapshot = chain.middleware
        snapshot.append(m)
        assert chain.middleware == [m]  # mutating the snapshot didn't affect the chain

    def test_construction_does_not_mutate_caller_list(self):
        @wrap_node
        async def m(call, *a, **k):
            return await call(*a, **k)

        original = [m]
        chain = MiddlewareChain(original)
        chain.add_middleware(m)
        assert original == [m]
