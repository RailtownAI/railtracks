"""Tests for the unified middleware primitives + MiddlewareSet engine.

    Wrapper   — execution control (wraps the inner callable)
    Gateway   — direction-less data transform; the slot it is placed in
                (gateway_entry vs gateway_exit) decides when it runs
    MiddlewareSet — ordered bands: outer_wrappers -> gateway_entry
                    -> inner_wrappers -> core -> gateway_exit
                    (with internal sys/user layers)
"""

import pytest

from railtracks.middleware import Gateway, MiddlewareSet, Wrapper, gateway, wrapper
from railtracks.middleware.set import _LayeredList


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------


class TestWrapper:
    def test_wrapper_requires_callable(self):
        with pytest.raises(TypeError, match="callable"):
            wrapper(123)  # type: ignore[arg-type]

    def test_wrapper_requires_async(self):
        # A wrapper must await the inner call, so a sync function is rejected.
        with pytest.raises(TypeError, match="async"):
            wrapper(lambda call: call)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_wrapper_wraps_and_calls(self):
        @wrapper
        async def double_call(call, *args, **kwargs):
            first = await call(*args, **kwargs)
            return first * 2

        async def core(x):
            return x + 1

        wrapped = double_call.wrap(core)
        assert await wrapped(4) == 10  # (4+1)*2

    @pytest.mark.asyncio
    async def test_wrapper_can_short_circuit(self):
        @wrapper
        async def never(call, *args, **kwargs):
            return "blocked"

        async def core():
            raise AssertionError("core should not run")

        assert await never.wrap(core)() == "blocked"


class TestGateway:
    def test_gateway_requires_callable(self):
        with pytest.raises(TypeError, match="callable"):
            Gateway(123)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_sync_gateway_is_adapted(self):
        # A plain `def` gateway is accepted and run inline.
        @gateway
        def shout(result):
            return result + "!"

        assert await shout.apply_exit("hi") == "hi!"

    @pytest.mark.asyncio
    async def test_sync_entry_gateway_is_adapted(self):
        @gateway
        def strip_in(text):
            return (text.strip(),), {}

        assert await strip_in.apply_entry("  hi  ") == (("hi",), {})

    def test_decorator_builds_gateway(self):
        @gateway
        async def g(*args, **kwargs):
            return args, kwargs

        assert isinstance(g, Gateway)

    @pytest.mark.asyncio
    async def test_entry_bare_value_raises(self):
        # No single-value shorthand: a bare value is ambiguous and rejected.
        @gateway
        async def upper(text):
            return text.upper()

        with pytest.raises(TypeError, match="must return None"):
            await upper.apply_entry("hi")

    @pytest.mark.asyncio
    async def test_entry_tuple_is_positional_args(self):
        @gateway
        async def pair(*args, **kwargs):
            return (1, 2)  # tuple -> positional args only

        assert await pair.apply_entry("x") == ((1, 2), {})

    @pytest.mark.asyncio
    async def test_entry_dict_is_keyword_args(self):
        @gateway
        async def kw(*args, **kwargs):
            return {"k": 3}  # dict -> keyword args only

        assert await kw.apply_entry("x") == ((), {"k": 3})

    @pytest.mark.asyncio
    async def test_entry_explicit_args_kwargs_tuple(self):
        @gateway
        async def reshape(*args, **kwargs):
            return (1, 2), {"k": 3}

        assert await reshape.apply_entry("x") == ((1, 2), {"k": 3})

    @pytest.mark.asyncio
    async def test_entry_gateway_args_helper(self):
        @gateway
        async def reorder(a, b):
            return gateway.args(b, a, flag=True)

        assert await reorder.apply_entry(1, 2) == ((2, 1), {"flag": True})

    @pytest.mark.asyncio
    async def test_check_only_entry_gateway_passes_through(self):
        # Returning None == "inspected only, don't change the call".
        seen = []

        @gateway
        async def log(*args, **kwargs):
            seen.append((args, kwargs))

        assert await log.apply_entry("hi", n=1) == (("hi",), {"n": 1})
        assert seen == [(("hi",), {"n": 1})]

    @pytest.mark.asyncio
    async def test_check_only_exit_gateway_passes_through(self):
        @gateway
        async def audit(result):
            pass  # returns None -> original result kept

        assert await audit.apply_exit("unchanged") == "unchanged"

    @pytest.mark.asyncio
    async def test_exit_transforms_result(self):
        @gateway
        async def shout(result):
            return result.upper()

        assert await shout.apply_exit("hi") == "HI"

    @pytest.mark.asyncio
    async def test_same_gateway_object_can_serve_either_slot(self):
        # A gateway carries no direction; apply_entry / apply_exit pick behaviour.
        @gateway
        async def passthrough(*args, **kwargs):
            return args, kwargs

        assert await passthrough.apply_entry(1, x=2) == ((1,), {"x": 2})


# ---------------------------------------------------------------------------
# _LayeredList
# ---------------------------------------------------------------------------


class TestLayeredList:
    def test_user_layer_only_iter(self):
        layers = _LayeredList(["a", "b"])
        layers.add_sys_before("s0")
        layers.add_sys_after("s1")
        assert list(layers) == ["a", "b"]
        assert len(layers) == 2

    def test_execution_order(self):
        layers = _LayeredList(["u"])
        layers.add_sys_before("before")
        layers.add_sys_after("after")
        assert layers.ordered() == ["before", "u", "after"]

    def test_sys_add_idempotent(self):
        layers = _LayeredList()
        layers.add_sys_before("x")
        layers.add_sys_before("x")
        assert layers.ordered() == ["x"]

    def test_copy_user_only_resets_sys(self):
        layers = _LayeredList(["u"])
        layers.add_sys_before("s")
        copy = layers.copy_user_only()
        assert list(copy) == ["u"]
        assert copy.ordered() == ["u"]

    def test_original_list_not_mutated(self):
        original = ["u"]
        layers = _LayeredList(original)
        layers.add_sys_before("s")
        assert original == ["u"]


# ---------------------------------------------------------------------------
# MiddlewareSet construction / coercion
# ---------------------------------------------------------------------------


def _noop_gateway():
    @gateway
    async def g(*args, **kwargs):
        return args, kwargs

    return g


def _noop_wrapper():
    @wrapper
    async def w(call, *args, **kwargs):
        return await call(*args, **kwargs)

    return w


class TestMiddlewareSetConstruction:
    def test_empty(self):
        ms = MiddlewareSet()
        assert ms.outer_wrappers == []
        assert ms.gateway_entry == []
        assert ms.gateway_exit == []
        assert ms.inner_wrappers == []

    def test_explicit_entry_and_exit(self):
        g_in, g_out = _noop_gateway(), _noop_gateway()
        ms = MiddlewareSet(gateway_entry=[g_in], gateway_exit=[g_out])
        assert ms.gateway_entry == [g_in]
        assert ms.gateway_exit == [g_out]

    def test_coerce_none(self):
        assert isinstance(MiddlewareSet.coerce(None), MiddlewareSet)

    def test_coerce_list_splits_by_type(self):
        g = _noop_gateway()
        w = _noop_wrapper()
        ms = MiddlewareSet.coerce([g, w])
        assert ms.gateway_entry == [g]   # bare-list gateways default to entry
        assert ms.outer_wrappers == [w]

    def test_coerce_rejects_non_middleware(self):
        with pytest.raises(TypeError):
            MiddlewareSet.coerce([object()])

    def test_constructor_rejects_wrong_band_type(self):
        g = _noop_gateway()
        with pytest.raises(TypeError, match="Wrapper"):
            MiddlewareSet(outer_wrappers=[g])  # gateway in a wrapper band

    def test_coerce_middlewareset_is_fresh_copy(self):
        g = _noop_gateway()
        ms1 = MiddlewareSet(gateway_entry=[g])
        ms1.register_sys_gateway_entry(_noop_gateway())
        ms2 = MiddlewareSet.coerce(ms1)
        # user layer preserved, sys layer reset
        assert ms2.gateway_entry == [g]
        assert ms2._entry._sys_before == []

    def test_user_list_not_mutated_by_sys_registration(self):
        user = [_noop_gateway()]
        ms = MiddlewareSet(gateway_entry=user)
        ms.register_sys_gateway_entry(_noop_gateway())
        assert len(user) == 1


class TestMiddlewareSetSysRegistration:
    def test_sys_entry_runs_before_user_entry(self):
        user_g = _noop_gateway()
        ms = MiddlewareSet(gateway_entry=[user_g])
        sys_g = _noop_gateway()
        ms.register_sys_gateway_entry(sys_g)
        assert ms._entry.ordered() == [sys_g, user_g]

    def test_sys_exit_runs_after_user_exit(self):
        user_g = _noop_gateway()
        sys_g = _noop_gateway()
        ms = MiddlewareSet(gateway_exit=[user_g])
        ms.register_sys_gateway_exit(sys_g)
        assert ms._exit.ordered() == [user_g, sys_g]


# ---------------------------------------------------------------------------
# MiddlewareSet.run — the engine
# ---------------------------------------------------------------------------


class TestEngineExecution:
    @pytest.mark.asyncio
    async def test_bare_core(self):
        ms = MiddlewareSet()

        async def core(x):
            return x * 2

        assert await ms.run(core, (5,), {}) == 10

    @pytest.mark.asyncio
    async def test_entry_then_exit(self):
        @gateway
        async def add_one(x):
            return (x + 1,), {}

        @gateway
        async def times_ten(result):
            return result * 10

        ms = MiddlewareSet(gateway_entry=[add_one], gateway_exit=[times_ten])

        async def core(x):
            return x

        # core(5+1)=6 -> *10 = 60
        assert await ms.run(core, (5,), {}) == 60

    @pytest.mark.asyncio
    async def test_full_onion_order(self):
        trace = []

        @wrapper
        async def outer(call, *a, **k):
            trace.append("outer-in")
            r = await call(*a, **k)
            trace.append("outer-out")
            return r

        @gateway
        async def entry(*a, **k):
            trace.append("entry")
            return a, k

        @wrapper
        async def inner(call, *a, **k):
            trace.append("inner-in")
            r = await call(*a, **k)
            trace.append("inner-out")
            return r

        @gateway
        async def exit_(result):
            trace.append("exit")
            return result

        ms = MiddlewareSet(
            outer_wrappers=[outer],
            gateway_entry=[entry],
            gateway_exit=[exit_],
            inner_wrappers=[inner],
        )

        async def core():
            trace.append("core")
            return "done"

        assert await ms.run(core) == "done"
        assert trace == [
            "outer-in",
            "entry",
            "inner-in",
            "core",
            "inner-out",
            "exit",
            "outer-out",
        ]

    @pytest.mark.asyncio
    async def test_multiple_entry_gateways_in_order(self):
        order = []

        def make(tag):
            @gateway
            async def g(*a, **k):
                order.append(tag)
                return a, k

            return g

        ms = MiddlewareSet(gateway_entry=[make("a"), make("b"), make("c")])

        async def core():
            return None

        await ms.run(core)
        assert order == ["a", "b", "c"]
