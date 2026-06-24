"""The middleware container + execution engine shared by every entry point.

:class:`MiddlewareChain` bundles the middleware for one site and runs a core
callable through it in band order::

    wrappers
    └── entry_gate             (transform input args)
        └── inner_wrappers
            └── core              (node / func / model call)
        └── (unwind inner_wrappers)
    └── exit_gate              (transform output)
    └── (unwind wrappers)

Each band is a :class:`_LayeredList` with ``sys_before → user → sys_after``
layers so framework middleware can be injected without touching user lists.
The caller's list is always copied in — the original is never mutated.
"""

from __future__ import annotations

from typing import (
    Any,
    Awaitable,
    Callable,
    Generic,
    Iterable,
    Iterator,
    ParamSpec,
    TypeVar,
)

from railtracks.middleware.primitives import Gate, Wrapper

_T = TypeVar("_T")
_P = ParamSpec("_P")
_R = TypeVar("_R")


class _LayeredList(Generic[_T]):
    """Three-layer ordered list: ``sys_before → user → sys_after``.

    Public iteration (``__iter__``, ``__len__``, ``__getitem__``) exposes the
    user layer only. The user list is copied on construction and never mutated.
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
    """Coerce a wrapper slot: auto-wraps raw async functions, rejects :class:`Gate` objects."""
    result: list[Wrapper] = []
    for i, item in enumerate(items or []):
        if isinstance(item, Wrapper):
            result.append(item)
        elif isinstance(item, Gate):
            raise TypeError(
                f"Wrapper slot at index {i} got a Gate: {item!r}. "
                f"Gates belong in entry_gate / exit_gate."
            )
        else:
            # Raw async function (or anything else) -> Wrapper validates it.
            result.append(Wrapper(item))
    return result


def _coerce_gates(items: Iterable[Any] | None) -> list[Gate]:
    """Coerce a gate slot: auto-wraps raw functions, rejects :class:`Wrapper` objects."""
    result: list[Gate] = []
    for i, item in enumerate(items or []):
        if isinstance(item, Gate):
            result.append(item)
        elif isinstance(item, Wrapper):
            raise TypeError(
                f"Gate slot at index {i} got a Wrapper: {item!r}. "
                f"Wrappers belong in wrappers / inner_wrappers."
            )
        else:
            # Raw async function (or anything else) -> Gate validates it.
            result.append(Gate(item))
    return result


class MiddlewareChain(Generic[_P, _R]):
    """Ordered middleware attached to a single entry point.

    Entry and exit gates are separate constructor arguments so the execution
    order is explicit::

        MiddlewareChain(
            wrappers=[retry],     # outermost: wrap the entire call
            entry_gate=[scrub_pii],  # transforms input before core runs
            exit_gate=[redact],      # transforms output after core returns
            inner_wrappers=[cache],  # innermost: hugs the core, inside gates
        )

    Coerce from a bare list via :meth:`coerce` (``Wrapper`` → ``wrappers``,
    ``Gate`` → ``entry_gate``).
    """

    def __init__(
        self,
        wrappers: Iterable[Wrapper[_P, _R]] | None = None,
        entry_gate: Iterable[Gate[_P, tuple[tuple, dict[str, Any]]]]
        | None = None,
        exit_gate: Iterable[Gate[[_R], _R]] | None = None,
        inner_wrappers: Iterable[Wrapper[_P, _R]] | None = None,
    ) -> None:
        self._outer: _LayeredList[Wrapper[_P, _R]] = _LayeredList(
            _coerce_wrappers(wrappers)
        )
        self._entry: _LayeredList[Gate[Any, Any]] = _LayeredList(
            _coerce_gates(entry_gate)
        )
        self._exit: _LayeredList[Gate[Any, Any]] = _LayeredList(
            _coerce_gates(exit_gate)
        )
        self._inner: _LayeredList[Wrapper[_P, _R]] = _LayeredList(
            _coerce_wrappers(inner_wrappers)
        )

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    @classmethod
    def coerce(cls, value: "MiddlewareChain | Iterable[Any] | None") -> "MiddlewareChain":
        """Normalise input into a fresh :class:`MiddlewareChain`.

        - ``None``             → empty chain.
        - ``MiddlewareChain``  → fresh copy; user layers preserved, sys layers reset.
        - ``list``             → :class:`Wrapper` items → ``wrappers``,
          :class:`Gate` items → ``entry_gate``.

        In a bare list ``@wrapper`` / ``@gate`` are required — without a
        named slot a raw function's role is ambiguous. Use the explicit
        constructor to pass raw functions. The caller's input is never mutated.
        """
        if value is None:
            return cls()
        if isinstance(value, MiddlewareChain):
            return value._fresh_copy()
        if isinstance(value, (list, tuple)):
            outer: list[Wrapper] = []
            entry: list[Gate] = []
            for i, item in enumerate(value):
                if isinstance(item, Gate):
                    entry.append(item)
                elif isinstance(item, Wrapper):
                    outer.append(item)
                else:
                    raise TypeError(
                        f"Middleware item at index {i} must be a Wrapper or Gate: "
                        f"{item!r}. In a bare list the role is ambiguous — decorate it "
                        f"with @wrapper or @gate, or use the MiddlewareChain(...) "
                        f"constructor to place a raw function in an explicit slot."
                    )
            return cls(wrappers=outer, entry_gate=entry)
        raise TypeError(
            f"Expected a MiddlewareChain or a list of Wrapper/Gate, got {value!r}"
        )

    def _fresh_copy(self) -> "MiddlewareChain":
        """Copy carrying user layers; system layers reset for independent reuse."""
        new = MiddlewareChain.__new__(MiddlewareChain)
        new._outer = self._outer.copy_user_only()
        new._entry = self._entry.copy_user_only()
        new._exit = self._exit.copy_user_only()
        new._inner = self._inner.copy_user_only()
        return new

    # ------------------------------------------------------------------
    # System-middleware registration (never touches the user layer)
    # ------------------------------------------------------------------

    def register_sys_entry_gate(
        self, gw: Gate[_P, tuple[tuple, dict[str, Any]]]
    ) -> None:
        """Register a framework entry gate (runs before user entry gates)."""
        self._entry.add_sys_before(gw)

    def register_sys_exit_gate(self, gw: Gate[[_R], _R]) -> None:
        """Register a framework exit gate (runs after user exit gates)."""
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
    def wrappers(self) -> list[Wrapper[_P, _R]]:
        """User-layer outer wrappers (excludes system-registered layers)."""
        return list(self._outer)

    @property
    def inner_wrappers(self) -> list[Wrapper[_P, _R]]:
        """User-layer inner wrappers (excludes system-registered layers)."""
        return list(self._inner)

    @property
    def entry_gate(self) -> list[Gate[Any, Any]]:
        """User-layer entry gates (excludes system-registered layers)."""
        return list(self._entry)

    @property
    def exit_gate(self) -> list[Gate[Any, Any]]:
        """User-layer exit gates (excludes system-registered layers)."""
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
        """Thread ``core(*args, **kwargs)`` through all middleware in band order.

        Execution order (including system layers within each band):

        1. ``wrappers`` sys_before → user → sys_after  (outermost, entered first)
        2. ``entry_gate`` — transforms ``(args, kwargs)`` before the core
        3. ``inner_wrappers`` sys_before → user → sys_after
        4. ``core``
        5. ``inner_wrappers`` unwind  (inner → outer)
        6. ``exit_gate`` — transforms the return value
        7. ``wrappers`` unwind  (inner → outer, exited last)
        """
        entry = self._entry.ordered()
        exit_ = self._exit.ordered()

        inner = core
        for w in reversed(self._inner.ordered()):
            inner = w.wrap(inner)

        async def gated(*a: _P.args, **k: _P.kwargs) -> _R:
            for g in entry:
                # no typing remedy possible here until python allows the return type to the be a paramspec
                a, k = await g.apply_entry(*a, **k)  # noqa
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
            f"MiddlewareChain(outer={self._outer!r}, "
            f"entry={self._entry!r}, exit={self._exit!r}, inner={self._inner!r})"
        )
