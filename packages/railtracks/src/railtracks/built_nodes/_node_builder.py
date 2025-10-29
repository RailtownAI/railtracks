import functools
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

from railtracks.built_nodes.concrete import (
    DynamicFunctionNode,
    LLMBase,
)
from railtracks.built_nodes.concrete._tool_call_base import OutputLessToolCallLLMBase
from railtracks.llm import (
    ModelBase,
    Parameter,
    SystemMessage,
    Tool,
)
from railtracks.llm.type_mapping import TypeMapper
from railtracks.nodes.nodes import Node
from railtracks.validation.node_creation.validation import (
    _check_duplicate_param_names,
    _check_max_tool_calls,
    _check_system_message,
    _check_tool_params_and_details,
    check_connected_nodes,
)

_TNode = TypeVar("_TNode", bound=Node)
_P = ParamSpec("_P")


class NodeBuilder(Generic[_TNode]):
    """
    A flexible builder for dynamically creating Node subclasses with custom configuration.

    NodeBuilder allows you to programmatically construct new node classes through the railtracks framework,
    overriding methods and attributes such as pretty name, tool details, parameters, and LLM configuration.
    This is useful for classes that need small changes to existing classes like ToolCalling, Structured, or Terminal LLMs.
    See EasyUsageWrappers for examples of how to use this builder.

    Args:
        node_class (type[_TNode]): The base node class to extend (must be a subclass of Node).
        name (str, optional): Human-readable name for the node/tool (used for debugging and tool metadata).
        class_name (str, optional): The name of the generated class (defaults to 'Dynamic{node_class.__qualname__}').

    Returns:
        Type[_TNode]: The node subclass with the specified overrides and configurations.
    """

    def __init__(
        self,
        node_class: Type[_TNode],
        /,
        *,
        name: str | None = None,
        class_name: str | None = None,
        return_into: str | None = None,
        format_for_return: Callable[[Any], Any] | None = None,
        format_for_context: Callable[[Any], Any] | None = None,
    ):
        self._node_class = node_class
        self._name = class_name or f"Dynamic{node_class.__qualname__}"
        self._methods = {}

        if name is not None:
            self._with_override("name", classmethod(lambda cls: name or cls.__name__))

    def llm_base(
        self,
        llm: ModelBase | None,
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
        if llm is not None:
            self._with_override("get_llm", classmethod(lambda cls: llm))

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
        Configure the node subclass to have a output_schema method.

        This method creates a class wide method which returns the output model for the node,
        which in turn is used for validation and serialization of structured outputs.

        Args:
            schema (Type[BaseModel]): The pydantic model class to use for the node's output.
        """

        self._with_override("output_schema", classmethod(lambda cls: schema))

    def tool_calling_llm(
        self,
        connected_nodes: Iterable[Union[Type[Node], Callable]],
        max_tool_calls: int | None = None,
    ):
        """
        Configure the node subclass to have a tool_nodes method and max_tool_calls method.

        This method creates methods that are helpful for tool calling llms with their tools
        stored in tool_nodes and with a limit on the number of tool calls they can make.

        Args:
            connected_nodes (Set[Union[Type[Node], Callable]]): The nodes/tools/functions that this node can call.
            max_tool_calls (int): The maximum number of tool calls allowed during a single invocation.

        Raises:
            AssertionError: If the node class is not a subclass of a ToolCallingLLM in the RT framework.
        """
        assert issubclass(self._node_class, OutputLessToolCallLLMBase), (
            f"To perform this operation the node class we are building must be of type LLMBase but got {self._node_class}"
        )

        from railtracks import (
            function_node,
        )

        connected_nodes = {
            function_node(elem).node_type if isfunction(elem) else elem
            for elem in connected_nodes
        }

        if not isinstance(connected_nodes, set):
            connected_nodes = set(connected_nodes)

        _check_max_tool_calls(max_tool_calls)
        check_connected_nodes(connected_nodes, Node)

        self._with_override("tool_nodes", classmethod(lambda cls: connected_nodes))
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
        tool_params: list[Parameter] | None = None,
    ):
        pass

    def setup_function_node(
        self,
        func: Callable[_P, Coroutine[Any, Any, Any] | Any],
        tool_details: str | None = None,
        tool_params: list[Parameter] | None = None,
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

        self._with_override("func", classmethod_preserving_function_meta(func))

        self.override_tool_info(
            tool=Tool.from_function(func, details=tool_details, params=tool_params)
        )

    def tool_callable_llm(
        self,
        tool_details: str | None,
        tool_params: Set[Parameter] | None = None,
    ):
        """
        Configure the node subclass to have tool_info and prepare_tool method

        This method creates methods that are used if the node was going to be used as a tool itself.
        This will allow other nodes to know how to call and use this node as a tool.

        Args:
            tool_details (str or None): Description of the tool for LLM tool calling (used in metadata and UI).
            tool_params (Set[Parameter] or None): Parameters for the tool, used for input validation and metadata.

        Raises:
            AssertionError: If the node class is not a subclass of an RT LLM node.
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
        tool_params: dict[str, Any] | Set[Parameter] | None = None,
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
        tool_params: dict[str, Any] | Set[Parameter] = None,
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
            tool_params (Set[Parameter] or dict[str, Any], optional): Parameters for the tool.


        """

        if tool is not None:
            assert name is None and tool_details == "" and tool_params is None, (
                "If you pass a Tool object to override_tool_info, you cannot pass name, tool_details or tool_params."
            )
            self._with_override("tool_info", classmethod(lambda cls: tool))

        else:

            def tool_info(cls: Type[_TNode]) -> Tool:
                if name is None:
                    prettied_name = cls.name()
                    prettied_name = prettied_name.replace(" ", "_")
                else:
                    prettied_name = name

                return Tool(
                    name=prettied_name,
                    detail=tool_details,
                    parameters=tool_params,
                )

            self._with_override("tool_info", classmethod(tool_info))

    def _override_prepare_tool_llm(
        self, tool_params: dict[str, Any] | Set[Parameter] | None = None
    ):
        """
        Override the prepare_tool function specifically for LLM nodes.

        This uses the prepare_tool_message_history method from LLMBase to create a coherent
        instruction message from tool parameters.
        """

        assert issubclass(self._node_class, LLMBase), (
            f"You tried to add prepare_tool_llm to a non LLM Node of {type(self._node_class)}."
        )

        def prepare_tool(cls, **kwargs):
            # Use the shared implementation in LLMBase
            message_hist = cls.prepare_tool_message_history(kwargs, tool_params)
            return cls(message_hist)

        self._with_override("prepare_tool", classmethod(prepare_tool))

    def add_attribute(self, name: str, attribute, make_function: bool, *args, **kwargs):
        """
        Add or override an attribute or method on the dynamically built node class.
        This takes functions or values and can make them class methods or class fields

        Args:
            name (str): The name of the attribute or method to add/override.
            attribute: The value or function to set.
            make_function (bool): If True, will make the attribute a class method that can be called.
            *args: positional parameters if you are passing a function to be called
            **kwargs: keyword arguments if you are passing a function to be called

        Example:
            builder.add_attribute("my_attr", 42, make_function=False)
            builder.add_attribute("my_attr", 42, make_function=True)
            builder.add_attribute("my_method", lambda cls: ..., make_function=True)
        """
        if make_function:
            if callable(attribute):
                self._with_override(name, classmethod(attribute))
            else:
                self._with_override(name, classmethod(lambda cls: attribute))
        else:
            if callable(attribute):
                self._with_override(name, attribute(*args, **kwargs))
            else:
                self._with_override(name, attribute)

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

        casted_klass = cast(Type[_TNode], klass)  # Ensure type consistency

        return casted_klass


def classmethod_preserving_function_meta(func):
    @functools.wraps(func)
    def wrapper(cls, *args, **kwargs):
        return func(*args, **kwargs)

    return classmethod(wrapper)
