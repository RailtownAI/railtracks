from __future__ import annotations

from typing import (
    Any,
    Awaitable,
    Callable,
    Generic,
    Iterable,
    Iterator,
    Literal,
    ParamSpec,
    TypeVar,
    overload,
)

from railtracks.middleware.primitives import Wrapper

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

    def add_user(self, item: _T) -> None:
        """Append an item to the user layer.

        Unlike the system layers this does **not** deduplicate — appending the
        same middleware twice runs it twice, matching the constructor, which
        keeps duplicates in the list it is given.
        """
        self._user.append(item)

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


class MiddlewareChain(Generic[_P, _R]):
    def __init__(
        self,
        wrappers: Iterable[Wrapper[_P, _R]] | None = None,
    ) -> None:
        self._wrappers: list[Wrapper[_P, _R]] = list(wrappers) if wrappers is not None else []


    def add_wrapper(self, w: Wrapper[_P, _R]) -> None:
        """Append a user outer wrapper (outermost band). Runs around the whole call."""
        self._wrappers.append(w)


    @property
    def wrappers(self) -> list[Wrapper[_P, _R]]:
        """User-layer outer wrappers (excludes system-registered layers)."""
        return list(self._wrappers)


    async def run(
        self,
        core: Callable[_P, Awaitable[_R]],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> _R:
        func = core
        for w in reversed(self._wrappers):
            func = w.wrap(func)

        return await func(*args, **kwargs)

    def __repr__(self) -> str:
        return f"MiddlewareChain(wrapper={self._wrappers!r}, "
