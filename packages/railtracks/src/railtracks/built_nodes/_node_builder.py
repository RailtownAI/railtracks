from __future__ import annotations

import functools
from typing import (
    Any,
    Callable,
    Coroutine,
    Generic,
    Iterable,
    Literal,
    ParamSpec,
    Type,
    TypeVar,
    Union,
    cast,
    overload,
)

from pydantic import BaseModel

from railtracks.built_nodes.concrete.response import StringResponse, StructuredResponse
from railtracks.built_nodes.llm_helpers import (
    ModelInvoker,
    ModelSource,
    StreamingModelSource,
    llm_invoke_factory,
    llm_observe,
    llm_prepare_called_as_tool_factory,
    llm_stream_invoke_factory,
)
from railtracks.llm import (
    Parameter,
    SystemMessage,
    Tool,
)
from railtracks.llm.history import MessageHistory
from railtracks.llm.message import Message
from railtracks.llm.response import Response
from railtracks.llm.type_mapping import TypeMapper
from railtracks.middleware import MiddlewareChain
from railtracks.nodes.nodes import Node
from railtracks.prompts.prompt import context_injection_gateway
from railtracks.validation.node_creation.validation import (
    _check_duplicate_param_names,
    _check_tool_params_and_details,
)


def classmethod_preserving_function_meta(func):
    @functools.wraps(func)
    def wrapper(_cls, *args, **kwargs):
        return func(*args, **kwargs)

    return classmethod(wrapper)


_TNode = TypeVar("_TNode", bound=Node)
_P = ParamSpec("_P")
_T = TypeVar("_T")
_P2 = ParamSpec("_P2")
_T2 = TypeVar("_T2")
_R = TypeVar("_R", bound=StringResponse | StructuredResponse)
_TStructured = TypeVar("_TStructured", bound=BaseModel)

UserInput = Union[str, MessageHistory, list[Message]]


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

        self._invoke: Callable[_P, Coroutine[Any, Any, _T]] | None = None
        self._node_class: Literal["Tool", "Agent"] | None = None
        self._node_name: str | None = None

        self._tool_info: Callable[[], Tool] | None = None
        self._prepare_arguments: Callable[..., dict[str, Any]] | None = None

        self._frozen_middleware: MiddlewareChain = MiddlewareChain()

    # ------------------------------------------------------------------
    # Non-streaming overloads (stream=False, default)
    # ------------------------------------------------------------------

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
        middleware: MiddlewareChain[[UserInput], StringResponse] | None = None,
        model_middleware: MiddlewareChain[
            [MessageHistory, type[BaseModel] | None, list[Tool] | None], Response
        ]
        | None = None,
        context_injection: bool = True,
        stream: Literal[False] = ...,
    ) -> NodeBuilder[[UserInput], StringResponse]: ...

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
        middleware: MiddlewareChain[[UserInput], StructuredResponse[_TStructured]]
        | None = None,
        model_middleware: MiddlewareChain[
            [MessageHistory, type[BaseModel] | None, list[Tool] | None], Response
        ]
        | None = None,
        context_injection: bool = True,
        stream: Literal[False] = ...,
    ) -> NodeBuilder[[UserInput], StructuredResponse[_TStructured]]: ...

    # ------------------------------------------------------------------
    # Streaming overloads (stream=True — model must be StreamingModelSource)
    # ------------------------------------------------------------------

    @overload
    @classmethod
    def llm(
        cls,
        name: str,
        class_name: str | None = None,
        *,
        model: StreamingModelSource,
        system_message: SystemMessage | None = None,
        schema: None = None,
        connected_nodes: Iterable[Type[Node]] | None = None,
        tool_details: str | None = None,
        tool_params: list[Parameter] | None = None,
        middleware: MiddlewareChain[[UserInput], StringResponse] | None = None,
        model_middleware: MiddlewareChain[
            [MessageHistory, type[BaseModel] | None, list[Tool] | None], Response
        ]
        | None = None,
        context_injection: bool = True,
        stream: Literal[True],
    ) -> NodeBuilder[[UserInput], StringResponse]: ...

    @overload
    @classmethod
    def llm(
        cls,
        name: str,
        class_name: str | None = None,
        *,
        model: StreamingModelSource,
        system_message: SystemMessage | None = None,
        schema: Type[_TStructured],
        connected_nodes: Iterable[Type[Node]] | None = None,
        tool_details: str | None = None,
        tool_params: list[Parameter] | None = None,
        middleware: MiddlewareChain[[UserInput], StructuredResponse[_TStructured]]
        | None = None,
        model_middleware: MiddlewareChain[
            [MessageHistory, type[BaseModel] | None, list[Tool] | None], Response
        ]
        | None = None,
        context_injection: bool = True,
        stream: Literal[True],
    ) -> NodeBuilder[[UserInput], StructuredResponse[_TStructured]]: ...

    @classmethod
    def llm(
        cls,
        name: str,
        class_name: str | None = None,
        *,
        model: ModelSource | StreamingModelSource,
        system_message: SystemMessage | None = None,
        schema: Type[_TStructured] | None = None,
        connected_nodes: Iterable[Type[Node]] | None = None,
        tool_details: str | None = None,
        tool_params: list[Parameter] | None = None,
        middleware: MiddlewareChain[[UserInput], _R] | None = None,
        model_middleware: MiddlewareChain[
            [MessageHistory, type[BaseModel] | None, list[Tool] | None], Response
        ]
        | None = None,
        context_injection: bool = True,
        stream: bool = False,
    ) -> NodeBuilder[[UserInput], _R]:
        instance = cls()
        casted_instance = cast(NodeBuilder, instance)
        casted_instance._class_name = class_name or name
        casted_instance._node_name = name
        casted_instance._node_class = "Agent"

        model_invoker = ModelInvoker(model, middleware=model_middleware)

        # Context injection is the default behaviour for all LLM nodes: rt.context
        # variables are filled into prompt templates before the model call. It is
        # wired in here as a system gateway so it applies regardless of which
        # higher-level wrapper created the node. Disable per-node with
        # context_injection=False, or flow/session-wide via prompt_injection=False.
        if context_injection:
            model_invoker.register_sys_entry_gate(context_injection_gateway)

        # llm_observe is registered for non-streaming only; streaming observability
        # is a pass-through stub until the stream-logger ticket is implemented.
        if not stream:
            model_invoker.register_sys_wrapper(llm_observe)

        if stream:
            casted_instance._invoke = llm_stream_invoke_factory(
                model_invoker=model_invoker,
                system_message=system_message,
                tool_nodes=list(connected_nodes) if connected_nodes else None,
                schema=schema,
            )
        else:
            casted_instance._invoke = llm_invoke_factory(
                model_invoker=model_invoker,
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

        casted_instance._frozen_middleware = MiddlewareChain.coerce(middleware)

        return casted_instance

    @classmethod
    def _prepare_llm_tool(
        cls, name: str, tool_details: str, tool_params: list[Parameter] | None = None
    ):
        _check_tool_params_and_details(tool_params, tool_details)
        _check_duplicate_param_names(tool_params or [])

        tool = Tool(
            name=name.replace(" ", "_"),
            detail=tool_details,
            parameters=tool_params,
        )

        return tool

    # TODO: consider overload helpers to help with the typing

    @classmethod
    def function(
        cls,
        function: Callable[_P2, Coroutine[None, None, _T2]],
        class_name: str | None = None,
        name: str | None = None,
        *,
        middleware: MiddlewareChain[_P2, _T2] | None = None,
        tool_details: str | None = None,
        tool_params: list[Parameter] | Type[BaseModel] | dict[str, Any] | None = None,
        tool_info: Tool | None = None,
    ) -> NodeBuilder[_P2, _T2]:
        instance = cls()
        casted_instance = cast(NodeBuilder[_P2, _T2], instance)

        casted_instance._class_name = class_name or f"{function.__name__.capitalize()}"

        casted_instance._invoke = function
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

        casted_instance._frozen_middleware = MiddlewareChain.coerce(middleware)

        return casted_instance

    def construct_required(self) -> dict[str, Any]:
        async def invoke(_self, *args, **kwargs) -> _T:
            method = unpack(self._invoke)
            return await method(*args, **kwargs)

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
            "frozen_middleware": self._frozen_middleware,
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
