from __future__ import annotations

import asyncio
import functools
import inspect
from typing import Awaitable, Callable, Concatenate, ParamSpec, TypeVar, overload

from railtracks.middleware.core import Middleware, wrap_node
from railtracks.middleware.verdict import Verdict, VerifierRejectedError
from railtracks.utils.logging.create import get_rt_logger
from railtracks.utils.unpack import unpack_async_sync

logger = get_rt_logger(__name__)

_P = ParamSpec("_P")
_R = TypeVar("_R")

_ApproveFn = Callable[Concatenate[_R, _P], Verdict[_R] | Awaitable[Verdict[_R]]]

_POSITIONAL_KINDS = (
    inspect.Parameter.POSITIONAL_ONLY,
    inspect.Parameter.POSITIONAL_OR_KEYWORD,
)


def _require_result_first(approve_fn: Callable) -> None:
    params = list(inspect.signature(approve_fn).parameters.values())
    first_ok = (
        params and params[0].name == "result" and params[0].kind in _POSITIONAL_KINDS
    )

    if not first_ok:
        got = params[0].name if params else "no parameters"
        message = (
            "post_verifier's approve_fn must take `result` as its first "
            f"positional parameter, got {got!r}. post_verifier calls "
            "approve_fn(result, *args, **kwargs), e.g.:\n"
            "    def approve(result, *args, **kwargs) -> Verdict: ..."
        )
        raise TypeError(message)


@overload
def post_verifier(
    approve_fn: _ApproveFn[_R, _P],
    /,
    *,
    timeout: float | None = None,
    name: str | None = None,
) -> Middleware[_P, _R]: ...
@overload
def post_verifier(
    *, timeout: float | None = None, name: str | None = None
) -> Callable[[_ApproveFn[_R, _P]], Middleware[_P, _R]]: ...


def post_verifier(
    approve_fn: _ApproveFn[_R, _P] | None = None,
    /,
    *,
    timeout: float | None = None,
    name: str | None = None,
) -> Middleware[_P, _R] | Callable[[_ApproveFn[_R, _P]], Middleware[_P, _R]]:
    """Build a node-verification middleware around ``approve_fn`` that gates a
    call's OUTPUT AFTER it has already run.

    The wrapped node always runs first. ``approve_fn`` is then called with the
    produced value as its first argument, followed by the node's own
    ``*args, **kwargs`` — sync or async, both supported — and must return a
    `Verdict`. ``result`` comes first (rather than trailing as a keyword) so
    the whole call is statically checkable: a `Verdict` mistyped against the
    node's actual return type, or an ``approve_fn`` with the wrong shape, is
    a type-checker error instead of a runtime surprise.

    Decline can't undo the call (it already happened) but still raises
    `VerifierRejectedError`, stopping the result from propagating onward. On
    accept, the result propagates using the verdict's ``result`` if it
    supplied an override, otherwise the original result unchanged.

    If ``timeout`` is set and ``approve_fn`` doesn't respond in time, the call
    is treated as declined with reason ``"timeout"``.

    ``approve_fn``'s shape is checked eagerly, when ``post_verifier(...)`` is
    called -- not deferred to the first real invocation. An ``approve_fn``
    that doesn't take ``result`` as its first positional parameter raises
    `TypeError` immediately, with a message naming what was found instead.

    See also :func:`~railtracks.prebuilt.middleware.pre_verifier.pre_verifier`,
    which gates whether a call happens at all, BEFORE it runs.
    """

    if approve_fn is None:
        return lambda fn: post_verifier(fn, timeout=timeout, name=name)

    _require_result_first(approve_fn)
    return wrap_node(_wrapper(approve_fn, timeout), name=name)


def _wrapper(approve_fn: _ApproveFn[_R, _P], timeout: float | None):
    @functools.wraps(approve_fn)
    async def wrapped(
        call: Callable[_P, Awaitable[_R]], *args: _P.args, **kwargs: _P.kwargs
    ) -> _R:
        result = await call(*args, **kwargs)

        try:
            review = unpack_async_sync(approve_fn(result, *args, **kwargs))
            if timeout is None:
                verdict = await review
            else:
                verdict = await asyncio.wait_for(review, timeout=timeout)
        except asyncio.TimeoutError:
            verdict = Verdict(accepted=False, comment="timeout")

        if not verdict.accepted:
            raise VerifierRejectedError(verdict.comment or "rejected")

        if verdict.comment:
            logger.info("post_verifier accepted with comment: %s", verdict.comment)

        return verdict.result if verdict.result is not None else result

    return wrapped
