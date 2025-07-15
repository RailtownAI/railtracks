import warnings
from typing import TypeVar, Generic, Dict, Any, cast, Type, Iterable, Set
from inspect import isfunction
from mcp import StdioServerParameters

from requestcompletion.llm import Parameter
from ...library._llm_base import LLMBase
from ...library.tool_calling_llms._base import OutputLessToolCallLLM
from ...library.tool_calling_llms.tool_call_llm import ToolCallLLM
from ....nodes.nodes import Node
from requestcompletion.exceptions.node_creation.validation import (
    _check_tool_params_and_details,
    _check_duplicate_param_names,
    _check_system_message,
    _check_max_tool_calls,
    check_connected_nodes,
)
from ....llm import (
    MessageHistory,
    UserMessage,
)
from ...library.function import from_function
import requestcompletion as rc
from pydantic import BaseModel

_TNode = TypeVar("_TNode", bound=Node)


class NodeBuilder(Generic[_TNode]):
    def __init__(
        self,
        node_class: type[_TNode],
        /,
        *,
        pretty_name: str | None = None,
        class_name: str | None = None,
        tool_details: str | None = None,
        tool_params: set[Parameter] | None = None,
    ):
        _check_tool_params_and_details(tool_params, tool_details)
        self._node_class = node_class
        self._name = class_name or f"Dynamic{node_class.__qualname__}"
        self._methods = {}
        if pretty_name is not None:
            self._with_override(
                "pretty_name", classmethod(lambda cls: pretty_name or cls.__name__)
            )

    def llm_base(
        self,
        llm_model: rc.llm.ModelBase | None,
        system_message: str | None = None,
    ):
        assert issubclass(self._node_class, LLMBase), (
            f"To perform this operation the node class we are building must be of type LLMBase but got {self._node_class}"
        )
        if llm_model is not None:
            if callable(llm_model):
                self._with_override("get_llm_model", classmethod(lambda cls: llm_model()))
            else:
                self._with_override("get_llm_model", classmethod(lambda cls: llm_model))

        _check_system_message(system_message)
        self._with_override("system_message", classmethod(lambda cls: system_message))

    def structured(
        self,
        output_model: Type[BaseModel],
    ):
        self._with_override("output_model", classmethod(lambda cls: output_model))

    def tool_calling_llm(
        self, connected_nodes: Dict[str, Any] | Set[Type[Node]], max_tool_calls: int
    ):
        assert issubclass(self._node_class, OutputLessToolCallLLM), (
            f"To perform this operation the node class we are building must be of type LLMBase but got {self._node_class}"
        )
        for elem in connected_nodes:
            if isfunction(elem):
                connected_nodes.remove(elem)
                connected_nodes.add(from_function(elem))
        if isinstance(connected_nodes, set):
            connected_nodes = {x: None for x in connected_nodes}
        _check_max_tool_calls(max_tool_calls)
        check_connected_nodes(connected_nodes, Node)
        self._with_override("connected_nodes", classmethod(lambda cls: connected_nodes))
        self._with_override("max_tool_calls", max_tool_calls)

    def mcp_llm(self, mcp_command, mcp_args, mcp_env, max_tool_calls):
        assert issubclass(self._node_class, ToolCallLLM), (
            f"To perform this operation the node class we are building must be of type LLMBase but got {self._node_class}"
        )
        tools = rc.nodes.library.from_mcp_server(
            StdioServerParameters(
                command=mcp_command,
                args=mcp_args,
                env=mcp_env if mcp_env is not None else None,
            )
        )
        connected_nodes = {*tools}
        _check_max_tool_calls(max_tool_calls)
        check_connected_nodes(connected_nodes, self._node_class)
        if isinstance(connected_nodes, set):
            connected_nodes = {
                x: None for x in connected_nodes
            }  ######Need to investigate this and see whats going on##########
        self._with_override("connected_nodes", classmethod(lambda cls: connected_nodes))

    def tool_callable_llm(
        self,
        tool_details: str | None,
        tool_params: Iterable[Parameter] | None = None,
    ):
        assert issubclass(self._node_class, LLMBase), (
            f"You tried to add tool calling details to a non LLM Node of {type(self._node_class)}."
        )
        _check_tool_params_and_details(tool_params, tool_details)
        _check_duplicate_param_names(tool_params or [])
        self.override_tool_info(tool_details, tool_params)
        self.override_prepare_tool(tool_params)

    def override_tool_info(
        self, tool_details: str, tool_params: dict[str, Any] | Iterable[Parameter]
    ):
        """
        Override the tool_info function for the node.
        """

        def tool_info(cls: Type[_TNode]) -> rc.llm.Tool:
            return rc.llm.Tool(
                name=cls.pretty_name().replace(" ", "_"),
                detail=tool_details,
                parameters=tool_params,
            )

        self._with_override("tool_info", classmethod(tool_info))

    def override_prepare_tool(self, tool_params: dict[str, Any]):
        """
        Override the tool_info function for the node.
        """

        def prepare_tool(cls, tool_parameters: Dict[str, Any]):
            message_hist = MessageHistory(
                [
                    UserMessage(f"{param.name}: '{tool_parameters[param.name]}'")
                    for param in (tool_params if tool_params else [])
                ]
            )
            return cls(message_hist)

        self._with_override("prepare_tool", classmethod(prepare_tool))

    def _with_override(self, name: str, method):
        """
        Add an override method for the node.
        """
        if name in self._methods:
            warnings.warn(
                f"Overriding existing method {name} in {self._name}. This may lead to unexpected behavior.",
                stacklevel=2,
            )
        self._methods[name] = method

    def build(self):
        class_dict: Dict[str, Any] = {}
        class_dict.update(self._methods)

        klass = type(
            self._name,
            (self._node_class,),
            class_dict,
        )

        return cast(Type[_TNode], klass)
