import warnings
from inspect import isfunction
from typing import (
    Any,
    Callable,
    Coroutine,
    Dict,
    Generic,
    Iterable,
    ParamSpec,
    Set,
    Type,
    TypeVar,
    Union,
    cast,
    overload,
)

from pydantic import BaseModel

from requestcompletion.exceptions.node_creation.validation import (
    _check_duplicate_param_names,
    _check_max_tool_calls,
    _check_system_message,
    _check_tool_params_and_details,
    check_connected_nodes,
)
from requestcompletion.llm import Parameter
from requestcompletion.llm.type_mapping import TypeMapper
from requestcompletion.nodes.library.mcp_tool import from_mcp_server

from ....llm import MessageHistory, ModelBase, SystemMessage, Tool, UserMessage
from ....nodes.nodes import Node
from ....rc_mcp import MCPStdioParams
from ...library._llm_base import LLMBase
from ...library.tool_calling_llms._base import OutputLessToolCallLLM
from ...library.tool_calling_llms.tool_call_llm import ToolCallLLM
from ..function_base import DynamicFunctionNode

_TNode = TypeVar("_TNode", bound=Node)
_P = ParamSpec("_P")


class NodeBuilder(Generic[_TNode]):
    """
    A flexible builder for dynamically creating Node subclasses with custom configuration.

    NodeBuilder allows you to programmatically construct new node classes through the requestcompletion framework,
    overriding methods and attributes such as pretty name, tool details, parameters, and LLM configuration.
    This is useful for classes that need small changes to existing classes like ToolCalling, Structured, or Terminal LLMs.
    See EasyUsageWrappers for examples of how to use this builder.

    Args:
        node_class (type[_TNode]): The base node class to extend (must be a subclass of Node).
        pretty_name (str, optional): Human-readable name for the node/tool (used for debugging and tool metadata).
        class_name (str, optional): The name of the generated class (defaults to 'Dynamic{node_class.__qualname__}').

    Returns:
        Type[_TNode]: The node subclass with the specified overrides and configurations.
    """

    def __init__(
        self,
        node_class: type[_TNode],
        /,
        *,
        pretty_name: str | None = None,
        class_name: str | None = None,
        return_into: str | None = None,
        format_for_return: Callable[[Any], Any] | None = None,
        format_for_context: Callable[[Any], Any] | None = None,
    ):
        self._node_class = node_class
        self._name = class_name or f"Dynamic{node_class.__qualname__}"
        self._methods = {}
        if pretty_name is not None:
            self._with_override(
                "pretty_name", classmethod(lambda cls: pretty_name or cls.__name__)
            )
        if return_into is not None:
            self._with_override("return_into", classmethod(lambda cls: return_into))
        if format_for_context is not None:
            self._with_override(
                "format_for_context",
                classmethod(lambda cls, x: format_for_context(x)),
            )
        if format_for_return is not None:
            self._with_override(
                "format_for_return",
                classmethod(lambda cls, x: format_for_return(x)),
            )

    def llm_base(
        self,
        llm_model: ModelBase | None,
        system_message: SystemMessage | str | None = None,
    ):
        """
        Configure the node subclass to use a specific LLM model and system message.

        Args:
            llm_model (ModelBase or None): The LLM model instance or to use for this node. If callable, it will be called to get the model.
            system_message (SystemMessage or str or None, optional): The system prompt/message for the node. If not passed here, a system message can be passed at runtime.

        Raises:
            AssertionError: If the node class is not a subclass of LLMBase.
        """
        assert issubclass(self._node_class, LLMBase), (
            f"To perform this operation the node class we are building must be of type LLMBase but got {self._node_class}"
        )
        if llm_model is not None:
            # TODO fix whatever this is.
            if callable(llm_model):
                self._with_override(
                    "get_llm_model", classmethod(lambda cls: llm_model())
                )
            else:
                self._with_override("get_llm_model", classmethod(lambda cls: llm_model))

        # Handle system message being passed as a string
        if isinstance(system_message, str):
            system_message = SystemMessage(system_message)

        _check_system_message(system_message)
        self._with_override("system_message", classmethod(lambda cls: system_message))

    def structured(
        self,
        schema: Type[BaseModel],
    ):
        """
        Configure the node subclass to have a schema method.

        This method creates a class wide method which returns the output model for the node,
        which in turn is used for validation and serialization of structured outputs.

        Args:
            schema (Type[BaseModel]): The pydantic model class to use for the node's output.
        """

        self._with_override("schema", classmethod(lambda cls: schema))

    def struct_mess(self):
        self._with_override("structured_message", True)

    def tool_calling_llm(
        self, connected_nodes: Set[Union[Type[Node], Callable]], max_tool_calls: int
    ):
        """
        Configure the node subclass to have a connected_nodes method and max_tool_calls method.

        This method creates methods that are helpful for tool calling llms with their tools
        stored in connected_nodes and with a limit on the number of tool calls they can make.

        Args:
            connected_nodes (Set[Union[Type[Node], Callable]]): The nodes/tools/functions that this node can call.
            max_tool_calls (int): The maximum number of tool calls allowed during a single invocation.

        Raises:
            AssertionError: If the node class is not a subclass of a ToolCallingLLM in the RC framework.
        """
        assert issubclass(self._node_class, OutputLessToolCallLLM), (
            f"To perform this operation the node class we are building must be of type LLMBase but got {self._node_class}"
        )

        from ..function import from_function

        connected_nodes = {
            from_function(elem) if isfunction(elem) else elem
            for elem in connected_nodes
        }

        if not isinstance(connected_nodes, set):
            connected_nodes = set(connected_nodes)

        _check_max_tool_calls(max_tool_calls)
        check_connected_nodes(connected_nodes, Node)

        self._with_override("connected_nodes", classmethod(lambda cls: connected_nodes))
        self._with_override("max_tool_calls", max_tool_calls)

    def mcp_llm(self, mcp_command, mcp_args, mcp_env, max_tool_calls):
        """
        Configure the node subclass to use MCP (Model Context Protocol) tool calling.

        This method sets up the node to call tools via an MCP server, specifying the command, arguments,
        environment, and maximum tool calls.

        Args:
            mcp_command (str): The command to run the MCP server (e.g., 'npx').
            mcp_args (list): Arguments to pass to the MCP server command.
            mcp_env (dict or None): Environment variables for the MCP server process.
            max_tool_calls (int): Maximum number of tool calls allowed per invocation.

        Raises:
            AssertionError: If the node class is not a subclass of ToolCallLLM.
        """

        assert issubclass(self._node_class, ToolCallLLM), (
            f"To perform this operation the node class we are building must be of type LLMBase but got {self._node_class}"
        )
        tools = from_mcp_server(
            MCPStdioParams(
                command=mcp_command,
                args=mcp_args,
                env=mcp_env if mcp_env is not None else None,
            )
        )

        connected_nodes = {*tools}

        _check_max_tool_calls(max_tool_calls)
        check_connected_nodes(connected_nodes, self._node_class)

        self._with_override("connected_nodes", classmethod(lambda cls: connected_nodes))
        self._with_override("max_tool_calls", max_tool_calls)

    @overload
    def setup_function_node(
        self,
        func: Callable[_P, Coroutine[Any, Any, Any] | Any],
    ):
        pass

    @overload
    def setup_function_node(
        self,
        func: Callable[_P, Coroutine[Any, Any, Any] | Any],
        tool_details: str,
        tool_params: Iterable[Parameter] | None = None,
    ):
        pass

    def setup_function_node(
        self,
        func: Callable[_P, Coroutine[Any, Any, Any] | Any],
        tool_details: str | None = None,
        tool_params: Set[Parameter] | None = None,
    ):
        """
        Setups a function node with the provided details:

        Specifically that means the following:
        - Creates a type mapper which will convert dictionary parameters to the correct types
        - Sets up the function to be called when the node is invoked
        - If tool_details is provided, it will override the tool_info method to provide the tool details and parameters.
        - If not it will use the default Tool.from_function(func) to create the tool info. (this will use the docstring)
        """

        assert issubclass(self._node_class, DynamicFunctionNode)

        type_mapper = TypeMapper(func)

        self._with_override("type_mapper", classmethod(lambda cls: type_mapper))

        self._with_override(
            "func", classmethod(lambda cls, *args, **kwargs: func(*args, **kwargs))
        )

        self.override_tool_info(
            tool=Tool.from_function(func, details=tool_details, params=tool_params)
        )

    def tool_callable_llm(
        self,
        tool_details: str | None,
        tool_params: Iterable[Parameter] | None = None,
    ):
        """
        Configure the node subclass to have tool_info and prepare_tool method

        This method creates methods that are used if the node was going to be used as a tool itself.
        This will allow other nodes to know how to call and use this node as a tool.

        Args:
            tool_details (str or None): Description of the tool for LLM tool calling (used in metadata and UI).
            tool_params (Iterable[Parameter] or None): Parameters for the tool, used for input validation and metadata.

        Raises:
            AssertionError: If the node class is not a subclass of an RC LLM node.
        """
        assert issubclass(self._node_class, LLMBase), (
            f"You tried to add tool calling details to a non LLM Node of {type(self._node_class)}."
        )

        _check_tool_params_and_details(tool_params, tool_details)
        _check_duplicate_param_names(tool_params or [])
        self.override_tool_info(tool_details=tool_details, tool_params=tool_params)
        self._override_prepare_tool_llm(tool_params)

    @overload
    def override_tool_info(
        self,
        *,
        name: str = None,
        tool_details: str = "",
        tool_params: Iterable[Parameter] | None = None,
    ):
        pass

    @overload
    def override_tool_info(
        self,
        *,
        tool: Tool,
    ):
        pass

    def override_tool_info(
        self,
        *,
        tool: Tool = None,
        name: str = None,
        tool_details: str = "",
        tool_params: dict[str, Any] | Iterable[Parameter] = None,
    ):
        """
        Override the tool_info function for the node.

        You can either provide the tool information directly as a Tool object or you can present it as a component of
        its construction parameters (name, tool details, tool_params).

        Args:
            tool (Tool, optional): A Tool object containing the tool information.
            --------------------------------------------------------------
            name (str, optional): The name of the tool.
            tool_details (str, optional): A description of the tool for LLMs.
            tool_params (Iterable[Parameter] or dict[str, Any], optional): Parameters for the tool.


        """

        if tool is not None:
            assert name is None and tool_details == "" and tool_params is None, (
                "If you pass a Tool object to override_tool_info, you cannot pass name, tool_details or tool_params."
            )
            self._with_override("tool_info", classmethod(lambda cls: tool))

        else:

            def tool_info(cls: Type[_TNode]) -> Tool:
                if name is None:
                    prettied_name = cls.pretty_name()
                    prettied_name = prettied_name.replace(" ", "_")
                else:
                    prettied_name = name

                return Tool(
                    name=prettied_name,
                    detail=tool_details,
                    parameters=tool_params,
                )

            self._with_override("tool_info", classmethod(tool_info))

    def _override_prepare_tool_llm(self, tool_params: dict[str, Any]):
        """
        Override the prepare_tool function specifically for LLM nodes.
        """

        assert issubclass(self._node_class, LLMBase), (
            f"You tried to add prepare_tool_llm to a non LLM Node of {type(self._node_class)}."
        )

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
        """
        Construct and return the configured node subclass.

        This method creates a the node subclass that inherits from the specified base node class, applying all method
        and attribute overrides configured via the builder.

        Returns
        -------
        Type[_TNode]
            The dynamically generated node subclass with all specified overrides.

        """
        class_dict: Dict[str, Any] = {}
        class_dict.update(self._methods)

        klass = type(
            self._name,
            (self._node_class,),
            class_dict,
        )

        return cast(type[_TNode], klass)
