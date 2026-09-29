from __future__ import annotations

from copy import deepcopy
from typing import Generic, Iterable, Type, TypeVar, Union, cast, overload

from pydantic import BaseModel

from railtracks.built_nodes._node_builder import NodeBuilder
from railtracks.built_nodes._types import ModelSource
from railtracks.llm import Parameter, SystemMessage
from railtracks.llm.history import MessageHistory
from railtracks.llm.message import Message, UserMessage
from railtracks.llm.middleware import ModelMiddleware
from railtracks.middleware.core import Middleware
from railtracks.nodes.nodes import Node
from railtracks.validation.node_creation.validation import _check_duplicate_tool_names

from ._agent_tool import agent_tool_arguments, agent_tool_info
from .llm_helpers import llm_invoke_factory
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
        connected_nodes: Iterable[Type[Node]] | None,
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
        middleware: Iterable[Middleware[[UserInput], StructuredResponse[_TStructured]]]
        | Iterable[Middleware[[UserInput], StringResponse]]
        | None = None,
        model_middleware: Iterable[ModelMiddleware] | None = None,
    ) -> (
        LLMNodeBuilder[StructuredResponse[_TStructured]]
        | LLMNodeBuilder[StringResponse]
    ):
        instance = cls()
        casted_instance = cast(LLMNodeBuilder, instance)
        casted_instance._class_name = class_name or name
        casted_instance._node_name = name
        casted_instance._node_class = "Agent"

        # Middleware are shared policy objects, not per-node payload state: a
        # MaxCalls budget or a Lock handed to two agents must be the same object
        # in both, and must stay the instance the caller still holds. Only the
        # list is copied.
        unwrapped_model_middleware: list[ModelMiddleware] = (
            list(model_middleware) if model_middleware is not None else []
        )
        unwrapped_middleware = list(middleware) if middleware is not None else []

        tool_nodes = list(deepcopy(connected_nodes)) if connected_nodes else None
        _check_duplicate_tool_names(tool_nodes)

        casted_instance._tool_nodes = tool_nodes

        casted_instance._invoke = llm_invoke_factory(
            model_source=model,
            system_message=system_message,
            tool_nodes=tool_nodes,
            schema=schema,
        )

        casted_instance._tool_info = agent_tool_info(
            agent_name=name,
            system_message=system_message,
            tool_details=tool_details,
            tool_params=tool_params,
        )
        casted_instance._prepare_arguments = agent_tool_arguments(tool_params)

        casted_instance._user_middleware = unwrapped_middleware
        casted_instance._user_model_middleware = unwrapped_model_middleware

        return casted_instance
