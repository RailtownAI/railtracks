"""Static regression cases for ``function_node`` middleware inference."""

from __future__ import annotations

from typing import TYPE_CHECKING, Awaitable, Callable

import railtracks as rt
from railtracks.middleware import Verdict
from railtracks.prebuilt.middleware import (
    Lock,
    MaxCalls,
    Retry,
    Timeout,
    post_verifier,
    pre_verifier,
)
from typing_extensions import assert_type

neutral_middleware = [
    Retry(max_tries=1),
    Timeout(seconds=5),
    MaxCalls(max_calls=3),
    Lock(),
]


@rt.function_node()
def empty_factory(value: str) -> int:
    return len(value)


@rt.function_node(middleware=[])
def empty_list(value: str) -> int:
    return len(value)


@rt.function_node(middleware=[Retry(max_tries=1)])
def one_prebuilt(value: str) -> int:
    return len(value)


@rt.function_node(middleware=neutral_middleware)
def reusable_for_strings(value: str) -> int:
    return len(value)


@rt.function_node(middleware=neutral_middleware)
def reusable_for_ints(value: int) -> str:
    return str(value)


@rt.function_node(middleware=[Retry(max_tries=1), Timeout(seconds=5)])
async def async_prebuilt(value: str) -> int:
    return len(value)


def approve_input(value: str) -> Verdict:
    return Verdict(accepted=bool(value))


def approve_output(result: int, value: str) -> Verdict[int]:
    return Verdict(accepted=result == len(value))


@rt.wrap_node
async def custom_middleware(call: Callable[[str], Awaitable[int]], value: str) -> int:
    return await call(value)


@rt.function_node(middleware=[pre_verifier(approve_input)])
def pre_only(value: str) -> int:
    return len(value)


@rt.function_node(middleware=[post_verifier(approve_output)])
def post_only(value: str) -> int:
    return len(value)


@rt.function_node(middleware=[Retry(max_tries=1), pre_verifier(approve_input)])
def pre_mixed(value: str) -> int:
    return len(value)


@rt.function_node(middleware=[post_verifier(approve_output), Timeout(seconds=5)])
def post_mixed(value: str) -> int:
    return len(value)


@rt.function_node(
    middleware=[
        Retry(max_tries=1),
        pre_verifier(approve_input),
        custom_middleware,
        post_verifier(approve_output),
        Timeout(seconds=5),
    ]
)
def fully_mixed(value: str) -> int:
    return len(value)


def direct_target(value: str) -> int:
    return len(value)


direct = rt.function_node(direct_target, middleware=neutral_middleware)

assert_type(empty_factory("value"), int)
assert_type(empty_list("value"), int)
assert_type(one_prebuilt("value"), int)
assert_type(reusable_for_strings("value"), int)
assert_type(reusable_for_ints(1), str)
assert_type(pre_only("value"), int)
assert_type(post_only("value"), int)
assert_type(pre_mixed("value"), int)
assert_type(post_mixed("value"), int)
assert_type(fully_mixed("value"), int)
assert_type(direct("value"), int)


async def check_async_signature() -> None:
    assert_type(await async_prebuilt("value"), int)


def approve_wrong_input(value: int) -> Verdict:
    return Verdict(accepted=value > 0)


def approve_wrong_output(result: str, value: str) -> Verdict[str]:
    return Verdict(accepted=result == value)


def approve_wrong_argument(result: int, value: int) -> Verdict[int]:
    return Verdict(accepted=result == value)


@rt.function_node(  # type: ignore[arg-type]
    middleware=[pre_verifier(approve_wrong_input)]
)
def rejected_pre_verifier(value: str) -> int:
    return len(value)


@rt.function_node(  # type: ignore[arg-type]
    middleware=[Retry(max_tries=1), post_verifier(approve_wrong_output)]
)
def rejected_mixed_verifier(value: str) -> int:
    return len(value)


@rt.function_node(  # type: ignore[arg-type]
    middleware=[post_verifier(approve_wrong_argument), Timeout(seconds=5)]
)
def rejected_post_argument(value: str) -> int:
    return len(value)


if TYPE_CHECKING:
    empty_factory(1)  # type: ignore[arg-type]
    rt.function_node(direct_target, middleware=[pre_verifier(approve_wrong_input)])  # type: ignore[misc, arg-type]
