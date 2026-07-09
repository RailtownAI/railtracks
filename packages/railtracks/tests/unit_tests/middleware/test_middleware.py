"""Tests for the unified middleware primitives + MiddlewareChain engine.

Wrapper   — execution control (wraps the inner callable)
Gate   — direction-less data transform; the slot it is placed in
            (entry_gate vs exit_gate) decides when it runs
MiddlewareChain — ordered bands: wrappers -> entry_gate
                -> inner_wrappers -> core -> exit_gate
                (with internal sys/user layers)
"""

import pytest
from railtracks.middleware import Gate, MiddlewareChain, Wrapper, gate, wrapper
from railtracks.middleware.set import _LayeredList

# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------


class TestWrapper:
    def test_wrapper_requires_callable(self):
        with pytest.raises(TypeError, match="callable"):
            wrapper(123)  # type: ignore[arg-type]

    def test_wrapper_requires_async(self):
        # A sync function is rejected immediately — wrappers must be async.
        with pytest.raises(TypeError, match="async"):
            wrapper(lambda call, *a, **k: call(*a, **k))  # type: ignore[arg-type]

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


class TestGate:
    def test_gate_requires_callable(self):
        with pytest.raises(TypeError, match="callable"):
            Gate(123)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_sync_gate_is_adapted(self):
        # A plain `def` gate is accepted and run inline.
        @gate
        def shout(result):
            return result + "!"

        assert await shout.apply_exit("hi") == "hi!"

    @pytest.mark.asyncio
    async def test_sync_entry_gate_is_adapted(self):
        @gate
        def strip_in(text):
            return (text.strip(),), {}

        assert await strip_in.apply_entry("  hi  ") == (("hi",), {})

    def test_decorator_builds_gate(self):
        @gate
        async def g(*args, **kwargs):
            return args, kwargs

        assert isinstance(g, Gate)

    def test_sync_gate_is_directly_callable(self):
        # __call__ is a raw passthrough to the underlying function (no slot semantics).
        @gate
        def tag(x):
            return f"[{x}]"

        assert tag("a") == "[a]"

    @pytest.mark.asyncio
    async def test_async_gate_call_returns_coroutine(self):
        seen = []

        @gate
        async def log(x):
            seen.append(x)
            return "raw"

        result = log("hi")  # async fn -> calling returns a coroutine
        assert await result == "raw"  # raw return, NOT the apply_entry interpretation
        assert seen == ["hi"]

    @pytest.mark.asyncio
    async def test_entry_bare_value_raises(self):
        # No single-value shorthand: a bare value is ambiguous and rejected.
        @gate
        async def upper(text):
            return text.upper()

        with pytest.raises(TypeError, match="must return None"):
            await upper.apply_entry("hi")

    @pytest.mark.asyncio
    async def test_entry_tuple_is_positional_args(self):
        @gate
        async def pair(*args, **kwargs):
            return (1, 2)  # tuple -> positional args only

        assert await pair.apply_entry("x") == ((1, 2), {})

    @pytest.mark.asyncio
    async def test_entry_dict_is_keyword_args(self):
        @gate
        async def kw(*args, **kwargs):
            return {"k": 3}  # dict -> keyword args only

        assert await kw.apply_entry("x") == ((), {"k": 3})

    @pytest.mark.asyncio
    async def test_entry_explicit_args_kwargs_tuple(self):
        @gate
        async def reshape(*args, **kwargs):
            return (1, 2), {"k": 3}

        assert await reshape.apply_entry("x") == ((1, 2), {"k": 3})

    @pytest.mark.asyncio
    async def test_entry_gate_args_helper(self):
        @gate
        async def reorder(a, b):
            return gate.args(b, a, flag=True)

        assert await reorder.apply_entry(1, 2) == ((2, 1), {"flag": True})

    @pytest.mark.asyncio
    async def test_check_only_entry_gate_passes_through(self):
        # Returning None == "inspected only, don't change the call".
        seen = []

        @gate
        async def log(*args, **kwargs):
            seen.append((args, kwargs))

        assert await log.apply_entry("hi", n=1) == (("hi",), {"n": 1})
        assert seen == [(("hi",), {"n": 1})]

    @pytest.mark.asyncio
    async def test_check_only_exit_gate_passes_through(self):
        @gate
        async def audit(result):
            pass  # returns None -> original result kept

        assert await audit.apply_exit("unchanged") == "unchanged"

    @pytest.mark.asyncio
    async def test_exit_transforms_result(self):
        @gate
        async def shout(result):
            return result.upper()

        assert await shout.apply_exit("hi") == "HI"

    @pytest.mark.asyncio
    async def test_same_gate_object_can_serve_either_slot(self):
        # A gate carries no direction; apply_entry / apply_exit pick behaviour.
        @gate
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
# MiddlewareChain construction / coercion
# ---------------------------------------------------------------------------


def _noop_gate():
    @gate
    async def g(*args, **kwargs):
        return args, kwargs

    return g


def _noop_wrapper():
    @wrapper
    async def w(call, *args, **kwargs):
        return await call(*args, **kwargs)

    return w


class TestMiddlewareChainConstruction:
    def test_empty(self):
        ms = MiddlewareChain()
        assert ms.wrappers == []
        assert ms.entry_gate == []
        assert ms.exit_gate == []
        assert ms.inner_wrappers == []

    def test_explicit_entry_and_exit(self):
        g_in, g_out = _noop_gate(), _noop_gate()
        ms = MiddlewareChain(entry_gate=[g_in], exit_gate=[g_out])
        assert ms.entry_gate == [g_in]
        assert ms.exit_gate == [g_out]

    def test_coerce_none(self):
        assert isinstance(MiddlewareChain.coerce(None), MiddlewareChain)

    def test_coerce_list_splits_by_type(self):
        g = _noop_gate()
        w = _noop_wrapper()
        ms = MiddlewareChain.coerce([g, w])
        assert ms.entry_gate == [g]  # bare-list gates default to entry
        assert ms.wrappers == [w]

    def test_coerce_rejects_non_middleware(self):
        with pytest.raises(TypeError):
            MiddlewareChain.coerce([object()])

    def test_constructor_rejects_wrong_band_type(self):
        g = _noop_gate()
        with pytest.raises(TypeError, match="Wrapper"):
            MiddlewareChain(wrappers=[g])  # gate in a wrapper band

    def test_coerce_middlewareset_is_fresh_copy(self):
        g = _noop_gate()
        ms1 = MiddlewareChain(entry_gate=[g])
        ms1.register_sys_gate(_noop_gate())
        ms2 = MiddlewareChain.coerce(ms1)
        # user layer preserved, sys layer reset
        assert ms2.entry_gate == [g]
        assert ms2._entry._sys_before == []

    def test_user_list_not_mutated_by_sys_registration(self):
        user = [_noop_gate()]
        ms = MiddlewareChain(entry_gate=user)
        ms.register_sys_gate(_noop_gate())
        assert len(user) == 1


class TestMiddlewareChainSysRegistration:
    def test_sys_entry_runs_before_user_entry(self):
        user_g = _noop_gate()
        ms = MiddlewareChain(entry_gate=[user_g])
        sys_g = _noop_gate()
        ms.register_sys_gate(sys_g)
        assert ms._entry.ordered() == [sys_g, user_g]

    def test_sys_exit_runs_after_user_exit(self):
        user_g = _noop_gate()
        sys_g = _noop_gate()
        ms = MiddlewareChain(exit_gate=[user_g])
        ms.register_sys_exit_gate(sys_g)
        assert ms._exit.ordered() == [user_g, sys_g]

    def test_sys_entry_position_before_is_default(self):
        user_g = _noop_gate()
        sys_g = _noop_gate()
        ms = MiddlewareChain(entry_gate=[user_g])
        ms.register_sys_gate(sys_g)  # default position="before"
        assert ms._entry.ordered() == [sys_g, user_g]

    def test_sys_entry_position_after_runs_last(self):
        user_g = _noop_gate()
        sys_g = _noop_gate()
        ms = MiddlewareChain(entry_gate=[user_g])
        ms.register_sys_gate(sys_g, position="after")
        assert ms._entry.ordered() == [user_g, sys_g]

    def test_sys_entry_before_and_after_bracket_user(self):
        user_g = _noop_gate()
        before_g = _noop_gate()
        after_g = _noop_gate()
        ms = MiddlewareChain(entry_gate=[user_g])
        ms.register_sys_gate(before_g, position="before")
        ms.register_sys_gate(after_g, position="after")
        assert ms._entry.ordered() == [before_g, user_g, after_g]

    @pytest.mark.asyncio
    async def test_sys_entry_after_runs_between_user_and_core(self):
        # Guardrail placement: a sys entry gate registered position="after" must
        # run after the user entry gate and immediately before the core.
        order = []

        def make(tag):
            @gate
            async def g(*a, **k):
                order.append(tag)
                return a, k

            return g

        ms = MiddlewareChain(entry_gate=[make("user")])
        ms.register_sys_gate(make("sys-before"), position="before")
        ms.register_sys_gate(make("sys-after"), position="after")

        async def core():
            order.append("core")

        await ms.run(core)
        assert order == ["sys-before", "user", "sys-after", "core"]


class TestMiddlewareChainUserRegistration:
    def test_add_appends_to_user_layer(self):
        w, ig, xg, iw = _noop_wrapper(), _noop_gate(), _noop_gate(), _noop_wrapper()
        ms = MiddlewareChain()
        ms.add_wrapper(w)
        ms.add_entry_gate(ig)
        ms.add_exit_gate(xg)
        ms.add_inner_wrapper(iw)
        assert ms.wrappers == [w]
        assert ms.entry_gate == [ig]
        assert ms.exit_gate == [xg]
        assert ms.inner_wrappers == [iw]

    def test_add_preserves_order_and_keeps_duplicates(self):
        a, b = _noop_gate(), _noop_gate()
        ms = MiddlewareChain(entry_gate=[a])
        ms.add_entry_gate(b)
        ms.add_entry_gate(a)  # user layer is not deduplicated
        assert ms.entry_gate == [a, b, a]

    def test_add_coerces_raw_function(self):
        async def raw_w(call, *a, **k):
            return await call(*a, **k)

        async def raw_g(*a, **k):
            return a, k

        ms = MiddlewareChain()
        ms.add_wrapper(raw_w)
        ms.add_entry_gate(raw_g)
        assert isinstance(ms.wrappers[0], Wrapper)
        assert isinstance(ms.entry_gate[0], Gate)

    def test_add_rejects_wrong_band_type(self):
        ms = MiddlewareChain()
        with pytest.raises(TypeError):
            ms.add_wrapper(_noop_gate())  # gate in a wrapper band
        with pytest.raises(TypeError):
            ms.add_entry_gate(_noop_wrapper())  # wrapper in a gate band


# ---------------------------------------------------------------------------
# MiddlewareChain.run — the engine
# ---------------------------------------------------------------------------


class TestEngineExecution:
    @pytest.mark.asyncio
    async def test_bare_core(self):
        ms = MiddlewareChain()

        async def core(x):
            return x * 2

        assert await ms.run(core, 5) == 10

    @pytest.mark.asyncio
    async def test_entry_then_exit(self):
        @gate
        async def add_one(x):
            return (x + 1,), {}

        @gate
        async def times_ten(result):
            return result * 10

        ms = MiddlewareChain(entry_gate=[add_one], exit_gate=[times_ten])

        async def core(x):
            return x

        # core(5+1)=6 -> *10 = 60
        assert await ms.run(core, 5) == 60

    @pytest.mark.asyncio
    async def test_full_onion_order(self):
        trace = []

        @wrapper
        async def outer(call, *a, **k):
            trace.append("outer-in")
            r = await call(*a, **k)
            trace.append("outer-out")
            return r

        @gate
        async def entry(*a, **k):
            trace.append("entry")
            return a, k

        @wrapper
        async def inner(call, *a, **k):
            trace.append("inner-in")
            r = await call(*a, **k)
            trace.append("inner-out")
            return r

        @gate
        async def exit_(result):
            trace.append("exit")
            return result

        ms = MiddlewareChain(
            wrappers=[outer],
            entry_gate=[entry],
            exit_gate=[exit_],
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
    async def test_multiple_entry_gates_in_order(self):
        order = []

        def make(tag):
            @gate
            async def g(*a, **k):
                order.append(tag)
                return a, k

            return g

        ms = MiddlewareChain(entry_gate=[make("a"), make("b"), make("c")])

        async def core():
            return None

        await ms.run(core)
        assert order == ["a", "b", "c"]
