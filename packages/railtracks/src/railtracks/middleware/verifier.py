from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable, ParamSpec, TypeVar, overload

from railtracks.utils.unpack import unpack_async_sync

from .core import Middleware, wrap_node

logger = logging.getLogger(__name__)

_P = ParamSpec("_P")
_R = TypeVar("_R")


@dataclass
class Verdict:
    """The result of an approve callable's review of a node call.

    - accept: ``accepted=True``, ``comment=None``
    - accept with comments: ``accepted=True``, ``comment=<str>``, optionally
      ``args``/``kwargs`` set to rewrite what gets forwarded to the node.
    - decline: ``accepted=False``, ``comment=None``
    - decline with comments: ``accepted=False``, ``comment=<str>``

    Overridden ``args``/``kwargs`` are forwarded as-is, with no validation
    against the node's original signature — a bad override surfaces as a
    ``TypeError`` from the node call itself.
    """

    accepted: bool
    comment: str | None = None
    args: tuple | None = None
    kwargs: dict | None = None


class VerifierRejectedError(Exception):
    """Raised when a verifier's approve callable declines a node call."""


_ApproveFn = Callable[_P, Verdict | Awaitable[Verdict]]


@overload
def verifier(
    approve_fn: _ApproveFn[_P],
    /,
    *,
    timeout: float | None = None,
    name: str | None = None,
) -> Middleware[_P, _R]: ...
@overload
def verifier(
    *, timeout: float | None = None, name: str | None = None
) -> Callable[[_ApproveFn[_P]], Middleware[_P, _R]]: ...


def verifier(
    approve_fn: _ApproveFn[_P] | None = None,
    /,
    *,
    timeout: float | None = None,
    name: str | None = None,
) -> Middleware[_P, _R] | Callable[[_ApproveFn[_P]], Middleware[_P, _R]]:
    """Build a general node-verification middleware around ``approve_fn``.

    ``approve_fn`` is called with the exact ``*args, **kwargs`` the wrapped
    node was called with — sync or async, both supported — and must return a
    `Verdict`. On decline, `VerifierRejectedError` is raised and the node's own
    body never runs. On accept, the call is forwarded onward, using the
    verdict's ``args``/``kwargs`` if it supplied overrides, otherwise the
    original ones unchanged.

    If ``timeout`` is set and ``approve_fn`` doesn't respond in time, the call
    is treated as declined with reason ``"timeout"``.
    """

    if approve_fn is None:
        return lambda fn: verifier(fn, timeout=timeout, name=name)

    return wrap_node(_wrapper(approve_fn, timeout), name=name)


def _wrapper(approve_fn: _ApproveFn[_P], timeout: float | None):
    async def wrapped(
        call: Callable[_P, Awaitable[_R]], *args: _P.args, **kwargs: _P.kwargs
    ) -> _R:
        try:
            review = unpack_async_sync(approve_fn(*args, **kwargs))
            if timeout is None:
                verdict = await review
            else:
                verdict = await asyncio.wait_for(review, timeout=timeout)
        except asyncio.TimeoutError:
            verdict = Verdict(accepted=False, comment="timeout")

        if not verdict.accepted:
            raise VerifierRejectedError(verdict.comment or "rejected")

        if verdict.comment:
            logger.info("verifier accepted with comment: %s", verdict.comment)

        new_args = verdict.args if verdict.args is not None else args
        new_kwargs = verdict.kwargs if verdict.kwargs is not None else kwargs
        return await call(*new_args, **new_kwargs)

    return wrapped
