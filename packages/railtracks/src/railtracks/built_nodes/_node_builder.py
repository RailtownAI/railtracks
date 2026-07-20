from __future__ import annotations

import functools
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Concatenate,
    Coroutine,
    Generic,
    Literal,
    ParamSpec,
    Type,
    TypeVar,
)

from railtracks.llm import (
    Tool,
)
from railtracks.middleware.core import Middleware
from railtracks.nodes.nodes import Node

if TYPE_CHECKING:
    from railtracks.built_nodes.llm.middleware.core import ModelMiddleware


def classmethod_preserving_function_meta(func):
    @functools.wraps(func)
    def wrapper(_cls, *args, **kwargs):
        return func(*args, **kwargs)

    return classmethod(wrapper)


_P = ParamSpec("_P")
_T = TypeVar("_T")
_P2 = ParamSpec("_P2")
_T2 = TypeVar("_T2")


def unpack(item: _T | None, /) -> _T:
    if item is None:
        raise ValueError("Unpacked Item was None")
    return item


def safe_create_node(
    class_name: str,
    required_methods: dict[str, Any],
    optional_methods: dict[str, Any],
) -> Type[Node]:
    if class_name is None:
        raise ValueError("Class name cannot be None")

    for method_name in required_methods.keys():
        if method_name in optional_methods:
            raise ValueError(
                f"Required Method shares a name with an optional method: {method_name}"
            )

    deletions = set()
    for method_name in optional_methods.keys():
        if optional_methods[method_name] is None:
            deletions.add(method_name)

    for deletion in deletions:
        del optional_methods[deletion]

    class_dict = {**required_methods, **optional_methods}

    return type(class_name + "Node", (Node,), class_dict)


class NodeBuilder(Generic[_P, _T]):
    def __init__(self) -> None:
        self._class_name: str | None = None

        self._invoke: Callable[Concatenate[Node, _P], Coroutine[Any, Any, _T]] | None = None
        self._node_class: Literal["Tool", "Agent"] | None = None
        self._node_name: str | None = None

        self._tool_info: Callable[[], Tool] | None = None
        self._prepare_arguments: Callable[..., dict[str, Any]] | None = None

        self._user_middleware: list[Middleware[_P, _T]] = []
        self._exterior_middleware: list[Middleware[_P, _T]] = []
        self._interior_middleware: list[Middleware[_P, _T]] = []
        self._user_model_middleware: list[ModelMiddleware] = []

    def construct_required(self) -> dict[str, Any]:
        async def invoke(_self, *args, **kwargs) -> _T:
            method = unpack(self._invoke)
            return await method(_self, *args, **kwargs)

        return {
            "invoke": invoke,
            "type": classmethod_preserving_function_meta(
                lambda: unpack(self._node_class)
            ),
            "name": classmethod_preserving_function_meta(
                lambda: unpack(self._node_name)
            ),
        }

    def construct_optional(self) -> dict[str, Any]:
        return {
            "tool_info": self._construct_tool_info(),
            "prepare_args": self._construct_prepared_arguments(),
            "_user_middleware": self._user_middleware,
            "_exterior_middleware": self._exterior_middleware,
            "_interior_middleware": self._interior_middleware,
            "_user_model_middleware": self._user_model_middleware,
        }

    def _construct_prepared_arguments(self):
        if self._prepare_arguments is None:
            return None

        return classmethod_preserving_function_meta(
            lambda **kwargs: unpack(self._prepare_arguments)(**kwargs)
        )

    def _construct_tool_info(self):
        if self._tool_info is None:
            return None

        return classmethod_preserving_function_meta(lambda: unpack(self._tool_info)())

    def build(self) -> Type[Node[_P, _T]]:
        assert self._class_name is not None, (
            "Class name must be set before building the node."
        )

        return safe_create_node(
            self._class_name,
            self.construct_required(),
            self.construct_optional(),
        )
