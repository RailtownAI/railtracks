from __future__ import annotations

from typing import (
    Any,
    Callable,
    Coroutine,
    Iterable,
    ParamSpec,
    Type,
    TypeVar,
    cast,
)

from pydantic import BaseModel

from railtracks.llm import (
    Parameter,
    Tool,
)
from railtracks.llm.type_mapping import TypeMapper
from railtracks.middleware.core import Middleware

from .._node_builder import NodeBuilder

_P2 = ParamSpec("_P2")
_T2 = TypeVar("_T2")


class FunctionNodeBuilder(NodeBuilder):
    @classmethod
    def function(
        cls,
        function: Callable[_P2, Coroutine[None, None, _T2]],
        class_name: str | None = None,
        name: str | None = None,
        *,
        middleware: Iterable[Middleware[_P2, _T2]] | None = None,
        tool_details: str | None = None,
        tool_params: list[Parameter] | Type[BaseModel] | dict[str, Any] | None = None,
        tool_info: Tool | None = None,
    ) -> NodeBuilder[_P2, _T2]:
        instance = cls()
        casted_instance = cast(NodeBuilder[_P2, _T2], instance)

        casted_instance._class_name = class_name or f"{function.__name__.capitalize()}"

        async def wrapped_function(self, *args, **kwargs) -> _T2:
            return await function(*args, **kwargs)

        casted_instance._invoke = wrapped_function
        casted_instance._node_class = "Tool"
        casted_instance._node_name = name or function.__name__

        tm = TypeMapper(function)
        resolved_tool = (
            tool_info
            if tool_info is not None
            else Tool.from_function(function, details=tool_details, params=tool_params)
        )
        casted_instance._tool_info = lambda: resolved_tool

        casted_instance._prepare_arguments = tm.convert_kwargs_to_appropriate_types

        casted_instance._user_middleware = (
            list(middleware) if middleware is not None else []
        )

        return casted_instance
