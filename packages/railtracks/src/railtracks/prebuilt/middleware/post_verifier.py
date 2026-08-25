from __future__ import annotations

import asyncio
import functools
import logging
from typing import Awaitable, Callable, ParamSpec, TypeVar, overload

from railtracks.middleware.core import Middleware, wrap_node
from railtracks.middleware.verdict import Verdict, VerifierRejectedError
from railtracks.utils.unpack import unpack_async_sync

logger = logging.getLogger(__name__)

_P = ParamSpec("_P")
_R = TypeVar("_R")

_ApproveFn = Callable[_P, Verdict[_R] | Awaitable[Verdict[_R]]]


@overload
def post_verifier(
    approve_fn: _ApproveFn[_P, _R],
    /,
    *,
    timeout: float | None = None,
    name: str | None = None,
) -> Middleware[_P, _R]: ...
@overload
def post_verifier(
    *, timeout: float | None = None, name: str | None = None
) -> Callable[[_ApproveFn[_P, _R]], Middleware[_P, _R]]: ...


def post_verifier(
    approve_fn: _ApproveFn[_P, _R] | None = None,
    /,
    *,
    timeout: float | None = None,
    name: str | None = None,
) -> Middleware[_P, _R] | Callable[[_ApproveFn[_P, _R]], Middleware[_P, _R]]:
    """Build a node-verification middleware around ``approve_fn`` that gates a
    call's OUTPUT AFTER it has already run.

    The wrapped node always runs first. ``approve_fn`` is then called with the
    node's own ``*args, **kwargs`` plus the produced value as a ``result``
    keyword — sync or async, both supported — and must return a `Verdict`.

    Decline can't undo the call (it already happened) but still raises
    `VerifierRejectedError`, stopping the result from propagating onward. On
    accept, the result propagates using the verdict's ``result`` if it
    supplied an override, otherwise the original result unchanged.

    If ``timeout`` is set and ``approve_fn`` doesn't respond in time, the call
    is treated as declined with reason ``"timeout"``.

    See also :func:`~railtracks.prebuilt.middleware.pre_verifier.pre_verifier`,
    which gates whether a call happens at all, BEFORE it runs.
    """

    if approve_fn is None:
        return lambda fn: post_verifier(fn, timeout=timeout, name=name)

    return wrap_node(_wrapper(approve_fn, timeout), name=name)


def _wrapper(approve_fn: _ApproveFn[_P, _R], timeout: float | None):
    @functools.wraps(approve_fn)
    async def wrapped(
        call: Callable[_P, Awaitable[_R]], *args: _P.args, **kwargs: _P.kwargs
    ) -> _R:
        result = await call(*args, **kwargs)

        try:
            review = unpack_async_sync(approve_fn(*args, **kwargs, result=result))
            if timeout is None:
                verdict = await review
            else:
                verdict = await asyncio.wait_for(review, timeout=timeout)
        except asyncio.TimeoutError:
            verdict: Verdict[_R] = Verdict(accepted=False, comment="timeout")

        if not verdict.accepted:
            raise VerifierRejectedError(verdict.comment or "rejected")

        if verdict.comment:
            logger.info("post_verifier accepted with comment: %s", verdict.comment)

        return verdict.result if verdict.result is not None else result

    return wrapped
