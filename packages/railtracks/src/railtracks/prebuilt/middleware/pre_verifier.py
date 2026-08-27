from __future__ import annotations

import asyncio
import functools
from typing import Any, Awaitable, Callable, ParamSpec, TypeVar, overload

from railtracks.middleware.core import Middleware, wrap_node
from railtracks.middleware.verdict import Verdict, VerifierRejectedError
from railtracks.utils.logging.create import get_rt_logger
from railtracks.utils.unpack import unpack_async_sync

logger = get_rt_logger(__name__)

_P = ParamSpec("_P")
_R = TypeVar("_R")

_ApproveFn = Callable[_P, Verdict | Awaitable[Verdict]]


@overload
def pre_verifier(
    approve_fn: _ApproveFn[_P],
    /,
    *,
    timeout: float | None = None,
    name: str | None = None,
) -> Middleware[_P, Any]: ...
@overload
def pre_verifier(
    *, timeout: float | None = None, name: str | None = None
) -> Callable[[_ApproveFn[_P]], Middleware[_P, Any]]: ...


def pre_verifier(
    approve_fn: _ApproveFn[_P] | None = None,
    /,
    *,
    timeout: float | None = None,
    name: str | None = None,
) -> Middleware[_P, Any] | Callable[[_ApproveFn[_P]], Middleware[_P, Any]]:
    """Build a node-verification middleware around ``approve_fn`` that gates a call
    BEFORE it runs.

    ``approve_fn`` is called with the exact ``*args, **kwargs`` the wrapped
    node was called with — sync or async, both supported — and must return a
    `Verdict`. On decline, `VerifierRejectedError` is raised and the node's own
    body never runs. On accept, the call is forwarded onward, using the
    verdict's ``args``/``kwargs`` if it supplied overrides, otherwise the
    original ones unchanged.

    If ``timeout`` is set and ``approve_fn`` doesn't respond in time, the call
    is treated as declined with reason ``"timeout"``.

    See also :func:`~railtracks.prebuilt.middleware.post_verifier.post_verifier`,
    which gates a call's output AFTER it has already run.
    """

    if approve_fn is None:
        return lambda fn: pre_verifier(fn, timeout=timeout, name=name)

    return wrap_node(_wrapper(approve_fn, timeout), name=name)


def _wrapper(approve_fn: _ApproveFn[_P], timeout: float | None):
    @functools.wraps(approve_fn)
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
            logger.info("pre_verifier accepted with comment: %s", verdict.comment)

        new_args = verdict.args if verdict.args is not None else args
        new_kwargs = verdict.kwargs if verdict.kwargs is not None else kwargs
        return await call(*new_args, **new_kwargs)

    return wrapped
