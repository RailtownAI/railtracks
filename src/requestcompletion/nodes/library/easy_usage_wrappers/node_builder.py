import warnings
from copy import deepcopy
from typing import TypeVar, Generic, Dict, Any, cast, Type, overload, Iterable, Set
from inspect import isfunction
from mcp import StdioServerParameters

from requestcompletion.llm import Parameter
from ....nodes.library.structured_llm import StructuredLLM
from ...library._llm_base import LLMBase
from ...library.tool_calling_llms.mess_hist_tool_call_llm import MessageHistoryToolCallLLM
from ...library.tool_calling_llms.tool_call_llm import ToolCallLLM
from ....nodes.nodes import Node
from requestcompletion.exceptions.node_creation.validation import (
    _check_tool_params_and_details,
    _check_duplicate_param_names,
    _check_system_message,
    _check_pretty_name,
    _check_max_tool_calls,
    check_connected_nodes,)
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
    ):
        self._node_class = node_class
        self._name = class_name or f"Dynamic{node_class.__qualname__}"
        self._methods = {}
        self._with_override("pretty_name", classmethod(lambda cls: pretty_name or cls.__name__))

    def llm_base(
            self,
            model: rc.llm.ModelBase | None,
            system_message: rc.llm.SystemMessage | str | None = None,
    ):
        assert issubclass(self._node_class, LLMBase), "To preform this operation the node class we are building must be of type LLMBase"
        if model is not None:
            self._with_override("llm_model", classmethod(lambda cls: model))

        _check_system_message(system_message)
        system_message = rc.llm.SystemMessage(system_message)
        self._with_override("system_message", classmethod(lambda cls: system_message))

    def structured(
            self,
            output_model: Type[BaseModel],
    ):
        assert issubclass(self._node_class, StructuredLLM), "To preform this operation the node class we are building must be of type StructuredLLM"

        self._with_override("output_model", classmethod(lambda cls: output_model))

    def tool_calling_llm(self, connected_nodes: Dict[str, Any] | Set[Type[Node]], max_tool_calls: int):
        assert issubclass(self._node_class, ToolCallLLM), "To preform this operation the node class we are building must be of type LLMBase"
        for elem in connected_nodes:
            if isfunction(elem):
                        connected_nodes.remove(elem)
                        connected_nodes.add(from_function(elem))
        _check_max_tool_calls(max_tool_calls)
        check_connected_nodes(connected_nodes, self._node_class)
        if isinstance(connected_nodes, set):
            connected_nodes = {x: None for x in connected_nodes}
        self._with_override("connected_nodes", classmethod(lambda cls: connected_nodes))
    
    def mcp_llm(self, mcp_command, mcp_args, mcp_env, max_tool_calls):
        assert issubclass(self._node_class, ToolCallLLM), "To preform this operation the node class we are building must be of type LLMBase"
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
            connected_nodes = {x: None for x in connected_nodes} ######Need to investigate this and see whats going on##########
        self._with_override("connected_nodes", classmethod(lambda cls: connected_nodes))


    def tool_callable_llm(
            self,
            tool_details: str | None,
            tool_params: Iterable[Parameter] | None = None,
    ):
        assert issubclass(self._node_class, LLMBase), f"You tried to add tool calling details to a non LLM Node of {type(self._node_class)}."
        _check_tool_params_and_details(tool_params, tool_details)
        _check_duplicate_param_names(tool_params or [])
        _check_pretty_name(self.pretty_name, tool_details)
        self.override_tool_info(tool_details, tool_params)
        self.override_prepare_tool(tool_params)


    def override_tool_info(self, tool_details: str, tool_params: dict[str, Any] | Iterable[Parameter]):
            """
            Override the tool_info function for the node.
            """

            def tool_info(cls: Type[_TNode]) -> rc.llm.Tool:
                return rc.llm.Tool(
                    name=cls.pretty_name().replace(" ", "_"),
                    detail=tool_details,
                    parameters=tool_params if tool_params is not None else set(),
                )

            self._with_override("tool_info", classmethod(tool_info))

    def override_prepare_tool(self, tool_params : dict[str, Any]):
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
