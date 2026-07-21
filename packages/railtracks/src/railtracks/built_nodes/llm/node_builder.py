from __future__ import annotations

from copy import deepcopy
from typing import Generic, Iterable, Type, TypeVar, Union, cast, overload

from pydantic import BaseModel

from railtracks.built_nodes._node_builder import NodeBuilder, unpack
from railtracks.built_nodes._types import ModelSource
from railtracks.llm import Parameter, SystemMessage, Tool
from railtracks.llm.history import MessageHistory
from railtracks.llm.message import Message, UserMessage
from railtracks.middleware.core import Middleware
from railtracks.nodes.nodes import Node
from railtracks.validation.node_creation.validation import (
    _check_duplicate_param_names,
    _check_tool_params_and_details,
)

from .llm_helpers import llm_invoke_factory, llm_prepare_called_as_tool_factory
from .middleware.core import ModelMiddleware
from .response import StringResponse, StructuredResponse

_TStructured = TypeVar("_TStructured", bound=BaseModel)
_R = TypeVar("_R", bound=StringResponse | StructuredResponse)

UserInput = Union[str, MessageHistory, list[Message], UserMessage]


class LLMNodeBuilder(NodeBuilder[[UserInput], _R], Generic[_R]):
    @overload
    @classmethod
    def llm(
        cls,
        name: str,
        class_name: str | None = None,
        *,
        model: ModelSource,
        system_message: SystemMessage | None = None,
        schema: None = None,
        connected_nodes: Iterable[Type[Node]] | None = None,
        tool_details: str | None = None,
        tool_params: list[Parameter] | None = None,
        middleware: Iterable[Middleware[[UserInput], StringResponse]] | None = None,
        model_middleware: Iterable[ModelMiddleware] | None = None,
    ) -> LLMNodeBuilder[StringResponse]: ...

    @overload
    @classmethod
    def llm(
        cls,
        name: str,
        class_name: str | None = None,
        *,
        model: ModelSource,
        system_message: SystemMessage | None = None,
        schema: Type[_TStructured],
        connected_nodes: Iterable[Type[Node]] | None = None,
        tool_details: str | None = None,
        tool_params: list[Parameter] | None = None,
        middleware: Iterable[Middleware[[UserInput], StructuredResponse[_TStructured]]]
        | None = None,
        model_middleware: Iterable[ModelMiddleware] | None = None,
    ) -> LLMNodeBuilder[StructuredResponse[_TStructured]]: ...

    @classmethod
    def llm(
        cls,
        name: str,
        class_name: str | None = None,
        *,
        model: ModelSource,
        system_message: SystemMessage | None = None,
        schema: Type[_TStructured] | None = None,
        connected_nodes: Iterable[Type[Node]] | None = None,
        tool_details: str | None = None,
        tool_params: list[Parameter] | None = None,
        middleware: Iterable[
            Middleware[[UserInput], StructuredResponse[_TStructured] | StringResponse]
        ]
        | None = None,
        model_middleware: Iterable[ModelMiddleware] | None = None,
    ) -> LLMNodeBuilder[StructuredResponse[_TStructured] | StringResponse]:
        instance = cls()
        casted_instance = cast(LLMNodeBuilder, instance)
        casted_instance._class_name = class_name or name
        casted_instance._node_name = name
        casted_instance._node_class = "Agent"

        unwrapped_model_middleware: list[ModelMiddleware] = (
            list(deepcopy(model_middleware)) if model_middleware is not None else []
        )
        unwrapped_middleware = (
            list(deepcopy(middleware)) if middleware is not None else []
        )

        casted_instance._invoke = llm_invoke_factory(
            model_source=model,
            system_message=system_message,
            tool_nodes=list(connected_nodes) if connected_nodes else None,
            schema=schema,
        )

        if tool_details is not None:
            tool = cls._prepare_llm_tool(
                name=name, tool_details=tool_details, tool_params=tool_params
            )

            casted_instance._tool_info = lambda: tool
            casted_instance._prepare_arguments = lambda **kwargs: {
                "user_input": llm_prepare_called_as_tool_factory(unpack(tool_params))(
                    **kwargs
                )
            }

        casted_instance._user_middleware = unwrapped_middleware
        casted_instance._user_model_middleware = unwrapped_model_middleware

        return casted_instance

    @classmethod
    def _prepare_llm_tool(
        cls, name: str, tool_details: str, tool_params: list[Parameter] | None = None
    ):
        _check_tool_params_and_details(tool_params, tool_details)
        _check_duplicate_param_names(tool_params or [])

        name = name.replace(" ", "_")

        tool = Tool(
            name=name,
            detail=tool_details,
            parameters=tool_params,
        )

        return tool
