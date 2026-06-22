"""The middleware container + execution engine shared by every entry point.

A :class:`MiddlewareSet` bundles the middleware attached to one site and runs a
core callable through it. The agreed structure has two fixed wrapper layers
sandwiching a gateway band::

    wrappers
    └── entry gateways            (transform input)
        └── inner_wrappers
            └── core              (node / func / model call)
        └── (unwind inner_wrappers)
    └── exit gateways             (transform output)
    └── (unwind wrappers)

Each band is an internal :class:`_LayeredList` with three layers so that
**system-provided** middleware can be registered without ever touching the
**user-provided** list:

    [sys_before]  →  [user]  →  [sys_after]

- ``sys_before`` — framework middleware that runs before user middleware.
- ``user``       — exactly what the caller passed; copied in, never mutated.
- ``sys_after``  — framework middleware that runs after user middleware.

The caller's original list is copied into the user layer, so the object they
passed is never modified. When a ``MiddlewareSet`` is reused across nodes, each
site gets a fresh copy whose system layers are reset (every site registers its
own system middleware independently).
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Generic, Iterable, Iterator, TypeVar, ParamSpec

from railtracks.middleware.primitives import Gateway, Wrapper

_T = TypeVar("_T")
_P = ParamSpec("_P")
_R = TypeVar("_R")


class _LayeredList(Generic[_T]):
    """Three-layer ordered list: ``sys_before → user → sys_after``.

    The public iteration interface exposes the **user** layer only; the user
    list is copied on construction and never mutated thereafter.
    """

    def __init__(self, user: Iterable[_T] | None = None) -> None:
        self._sys_before: list[_T] = []
        self._user: list[_T] = list(user or [])
        self._sys_after: list[_T] = []

    def add_sys_before(self, item: _T) -> None:
        """Register a system item that runs before the user layer (idempotent)."""
        if item not in self._sys_before:
            self._sys_before.append(item)

    def add_sys_after(self, item: _T) -> None:
        """Register a system item that runs after the user layer (idempotent)."""
        if item not in self._sys_after:
            self._sys_after.append(item)

    def ordered(self) -> list[_T]:
        """Flat execution order: ``sys_before + user + sys_after``."""
        return self._sys_before + self._user + self._sys_after

    def copy_user_only(self) -> "_LayeredList[_T]":
        """A fresh copy carrying the user layer; system layers are reset."""
        return _LayeredList(list(self._user))

    # user-layer-only public view -------------------------------------------
    def __iter__(self) -> Iterator[_T]:
        return iter(self._user)

    def __len__(self) -> int:
        return len(self._user)

    def __getitem__(self, index: int) -> _T:
        return self._user[index]

    def __repr__(self) -> str:
        return (
            f"_LayeredList(sys_before={self._sys_before!r}, "
            f"user={self._user!r}, sys_after={self._sys_after!r})"
        )


def _coerce_wrappers(items: Iterable[Any] | None) -> list[Wrapper]:
    """Normalise a wrapper slot. The slot already tells us the role, so a raw
    async function is auto-wrapped — ``@wrapper`` is optional here. An already
    built :class:`Gateway` in a wrapper slot is the one thing we reject."""
    result: list[Wrapper] = []
    for i, item in enumerate(items or []):
        if isinstance(item, Wrapper):
            result.append(item)
        elif isinstance(item, Gateway):
            raise TypeError(
                f"Wrapper slot at index {i} got a Gateway: {item!r}. "
                f"Gateways belong in gateway_entry / gateway_exit."
            )
        else:
            # Raw async function (or anything else) -> Wrapper validates it.
            result.append(Wrapper(item))
    return result


def _coerce_gateways(items: Iterable[Any] | None) -> list[Gateway]:
    """Normalise a gateway slot. The slot already tells us the role, so a raw
    async function is auto-wrapped — ``@gateway`` is optional here. An already
    built :class:`Wrapper` in a gateway slot is the one thing we reject."""
    result: list[Gateway] = []
    for i, item in enumerate(items or []):
        if isinstance(item, Gateway):
            result.append(item)
        elif isinstance(item, Wrapper):
            raise TypeError(
                f"Gateway slot at index {i} got a Wrapper: {item!r}. "
                f"Wrappers belong in wrappers / inner_wrappers."
            )
        else:
            # Raw async function (or anything else) -> Gateway validates it.
            result.append(Gateway(item))
    return result


class MiddlewareSet(Generic[_P, _R]):
    """The ordered middleware attached to a single entry point.

    Construct with explicit bands — entry and exit gateways are **separate** lists
    so the execution order is obvious at the call site::

        MiddlewareSet(
            wrappers=[retry],  # outermost: wrap the whole call
            gateway_entry=[scrub_pii],  # run before the core (input transforms)
            gateway_exit=[redact],  # run after the core (output transforms)
            inner_wrappers=[cache],  # innermost: hug the core, inside the gateways
        )

    Or coerce from a bare list via :meth:`coerce` (``Wrapper`` items →
    ``wrappers``, ``Gateway`` items → ``gateway_entry``).
    """

    def __init__(
        self,
        wrappers: Iterable[Wrapper[_P, _R]] | None = None,
        gateway_entry: Iterable[Gateway[_P, tuple[tuple, dict[str, Any]]]] | None = None,
        gateway_exit: Iterable[Gateway[[_R], _R]] | None = None,
        inner_wrappers: Iterable[Wrapper[_P, _R]] | None = None,
    ) -> None:
        self._outer: _LayeredList[Wrapper[_P, _R]] = _LayeredList(_coerce_wrappers(wrappers))
        self._entry: _LayeredList[Gateway[_P, tuple[tuple, dict[str, Any]]]] = _LayeredList(
            _coerce_gateways(gateway_entry)
        )
        self._exit: _LayeredList[Gateway[[_R], _R]] = _LayeredList(_coerce_gateways(gateway_exit))
        self._inner: _LayeredList[Wrapper[_P, _R]] = _LayeredList(
            _coerce_wrappers(inner_wrappers)
        )

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    @classmethod
    def coerce(cls, value: "MiddlewareSet | Iterable[Any] | None") -> "MiddlewareSet":
        """Normalise user input into a fresh ``MiddlewareSet``.

        - ``None``           → empty set
        - ``MiddlewareSet``  → fresh copy (user layers preserved, sys layers reset)
        - ``list`` / iterable → ``Wrapper`` items go to ``wrappers``,
          ``Gateway`` items go to ``gateway_entry`` (the common case; use the
          explicit constructor for exit gateways)

        A bare list is the one place the ``@wrapper`` / ``@gateway`` decorator is
        still required: with no slot to imply the role, a raw async function is
        ambiguous. Use the explicit ``MiddlewareSet(...)`` constructor to pass
        raw functions.

        The caller's list / ``MiddlewareSet`` is never mutated.
        """
        if value is None:
            return cls()
        if isinstance(value, MiddlewareSet):
            return value._fresh_copy()
        if isinstance(value, (list, tuple)):
            outer: list[Wrapper] = []
            entry: list[Gateway] = []
            for i, item in enumerate(value):
                if isinstance(item, Gateway):
                    entry.append(item)
                elif isinstance(item, Wrapper):
                    outer.append(item)
                else:
                    raise TypeError(
                        f"Middleware item at index {i} must be a Wrapper or Gateway: "
                        f"{item!r}. In a bare list the role is ambiguous — decorate it "
                        f"with @wrapper or @gateway, or use the MiddlewareSet(...) "
                        f"constructor to place a raw function in an explicit slot."
                    )
            return cls(wrappers=outer, gateway_entry=entry)
        raise TypeError(
            f"Expected a MiddlewareSet or a list of Wrapper/Gateway, got {value!r}"
        )

    def _fresh_copy(self) -> "MiddlewareSet":
        """Copy carrying user layers; system layers reset for independent reuse."""
        new = MiddlewareSet.__new__(MiddlewareSet)
        new._outer = self._outer.copy_user_only()
        new._entry = self._entry.copy_user_only()
        new._exit = self._exit.copy_user_only()
        new._inner = self._inner.copy_user_only()
        return new

    # ------------------------------------------------------------------
    # System-middleware registration (never touches the user layer)
    # ------------------------------------------------------------------

    def register_sys_gateway_entry(self, gw: Gateway[_P, tuple[tuple, dict[str, Any]]]) -> None:
        """Register a framework entry gateway (runs before user entry gateways)."""
        self._entry.add_sys_before(gw)

    def register_sys_gateway_exit(self, gw: Gateway[[_R], _R]) -> None:
        """Register a framework exit gateway (runs after user exit gateways)."""
        self._exit.add_sys_after(gw)

    def register_sys_outer_wrapper(self, w: Wrapper[_P, _R]) -> None:
        """Register a framework wrapper outside all user (outer) wrappers."""
        self._outer.add_sys_before(w)

    def register_sys_inner_wrapper(self, w: Wrapper[_P, _R]) -> None:
        """Register a framework wrapper inside all user (inner) wrappers."""
        self._inner.add_sys_after(w)

    # ------------------------------------------------------------------
    # Read-only user views
    # ------------------------------------------------------------------

    @property
    def wrappers(self):
        return list(self._outer)

    @property
    def inner_wrappers(self):
        return list(self._inner)

    @property
    def gateway_entry(self):
        return list(self._entry)

    @property
    def gateway_exit(self):
        return list(self._exit)

    # ------------------------------------------------------------------
    # Execution engine
    # ------------------------------------------------------------------

    async def run(
        self,
        core: Callable[_P, Awaitable[_R]],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> _R:
        """Run ``core(*args, **kwargs)`` through this middleware set."""
        entry = self._entry.ordered()
        exit_ = self._exit.ordered()

        inner = core
        for w in reversed(self._inner.ordered()):
            inner = w.wrap(inner)

        async def gated(*a: _P.args, **k: _P.kwargs) -> _R:
            for g in entry:
                # no typing remedy possible here until python allows the return type to the be a paramspec
                a, k = await g.apply_entry(*a, **k) # noqa
            result = await inner(*a, **k)
            for g in exit_:
                result = await g.apply_exit(result)
            return result

        outer = gated
        for w in reversed(self._outer.ordered()):
            outer = w.wrap(outer)

        return await outer(*args, **kwargs)

    def __repr__(self) -> str:
        return (
            f"MiddlewareSet(outer={self._outer!r}, "
            f"entry={self._entry!r}, exit={self._exit!r}, inner={self._inner!r})"
        )
