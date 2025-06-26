import os
from mcp import StdioServerParameters
import warnings
from copy import deepcopy
from typing import Set, Type, Union, Literal, Dict, Any, Callable, TypeVar, Generic
from pydantic import BaseModel
from abc import ABC, abstractmethod
from requestcompletion.llm import (
    MessageHistory,
    ModelBase,
    SystemMessage,
    AssistantMessage,
    UserMessage,
    Tool,
)
from requestcompletion.nodes.library import structured_llm
from requestcompletion.nodes.library._tool_call_llm_base import (
    OutputLessToolCallLLM,
)
from requestcompletion.nodes.nodes import Node
from requestcompletion.llm.message import Role

from typing_extensions import Self
from requestcompletion.exceptions import NodeCreationError
from requestcompletion.exceptions.node_creation.validation import validate_tool_metadata
from requestcompletion.exceptions.node_invocation.validation import (
    check_model,
    check_message_history,
)
import requestcompletion as rc

_T = TypeVar("_T")


class MCPAgentBase(OutputLessToolCallLLM[_T], ABC, Generic[_T]):
    def __init_subclass__(
        cls,
        mcp_command: str | None = None,
        mcp_args: list[str] | None = None,
        mcp_env: dict[str, str] | None = None,
        api_token: str | None = None,
        pretty_name: str | None = None,
        model: ModelBase | None = None,
        system_message: SystemMessage | str | None = None,
        output_type: Literal["MessageHistory", "LastMessage"] = "LastMessage",
        output_model: BaseModel | None = None,
        tool_details: str | None = None,
        tool_params: dict | None = None,
    ):
        # Look to see if the user has set the NOTION_TOKEN environment variable
        if api_token is None:
            if os.getenv("NOTION_TOKEN"):
                api_token = os.getenv("NOTION_TOKEN")
            else:
                raise NodeCreationError(
                    "Notion API token not found",
                    [
                        "Please set a NOTION_TOKEN in your .env or pass it as a parameter to the notion_agent function."
                    ],
                )
        # Look to see if the user has set the NOTION_ROOT_PAGE_ID environment variable
        if os.getenv("NOTION_ROOT_PAGE_ID"):
            system_message = system_message + (
                f"Use the page with ID {os.getenv('NOTION_ROOT_PAGE_ID')} as the parent page for your operations."
            )

        tools = rc.nodes.library.from_mcp_server(
            StdioServerParameters(
                command=mcp_command,
                args=mcp_args,
                env=mcp_env if mcp_env is not None else None,
            )
        )
        connected_nodes = {*tools}

        validate_tool_metadata(tool_params, tool_details, system_message, pretty_name)
        if system_message is not None and isinstance(
            system_message, str
        ):  # system_message is a string, (tackled at the time of node creation)
            system_message = SystemMessage(system_message)

        # Initialize class wide variables passed by factory function
        cls._connected_nodes = connected_nodes
        cls.tool_params = tool_params
        cls.tool_details = tool_details
        cls._pretty_name = pretty_name
        cls._output_type = output_type
        cls._output_model = output_model
        cls.system_message = system_message
        cls.model = model

        # Now that attributes are set, we can validate the attributes
        super().__init_subclass__()

    def return_output(self):
        if self.__class__._output_model:
            if isinstance(self.structured_output, Exception):
                raise self.structured_output
            return self.structured_output
        elif self.__class__._output_type == "MessageHistory":
            return self.message_hist
        else:
            return self.message_hist[-1]

    def __init__(
        self,
        instructions: str,
        llm_model: ModelBase | None = None,
        max_tool_calls: int | None = 30,
    ):
        message_history = MessageHistory([UserMessage(instructions)])
        check_message_history(
            message_history, self.__class__.system_message
        )  # raises NodeInvocationError if any of the checks fail
        message_history_copy = deepcopy(message_history)
        if self.__class__.system_message is not None:
            if len([x for x in message_history_copy if x.role == Role.system]) > 0:
                warnings.warn(
                    "System message already exists in message history. We will replace it."
                )
                message_history_copy = [
                    x for x in message_history_copy if x.role != Role.system
                ]
                message_history_copy.insert(0, self.__class__.system_message)
            else:
                message_history_copy.insert(0, self.__class__.system_message)

        if llm_model is not None:
            if self.__class__.model is not None:
                warnings.warn(
                    "You have provided a model as a parameter and as a class variable. We will use the parameter."
                )
        else:
            check_model(
                self.__class__.model
            )  # raises NodeInvocationError if any of the checks fail
            llm_model = self.__class__.model

        super().__init__(message_history_copy, llm_model, max_tool_calls=max_tool_calls)

        if self.__class__._output_model:
            system_structured = SystemMessage(
                "You are a structured LLM that can convert the response into a structured output."
            )
            self.structured_resp_node = structured_llm(
                self.__class__._output_model,
                system_message=system_structured,
                model=llm_model,
            )

    @abstractmethod
    def connected_nodes(self) -> Set[Union[Type[Node], Callable]]:
        return

    @classmethod
    def pretty_name(cls) -> str:
        if cls._pretty_name is None:
            return (
                "ToolCallLLM("
                + ", ".join([x.pretty_name() for x in cls._connected_nodes])
                + ")"
            )
        else:
            return cls._pretty_name

    @classmethod
    def tool_info(cls):
        return Tool(
            name=cls.pretty_name().replace(" ", "_"),
            detail=cls.tool_details,
            parameters=cls.tool_params,
        )

    @classmethod
    def prepare_tool(cls, tool_parameters: Dict[str, Any]) -> Self:
        message_hist = MessageHistory(
            [
                UserMessage(f"{cls.param.name}: '{tool_parameters[param.name]}'")
                for param in (cls.tool_params if cls.tool_params else [])
            ]
        )
        return cls(message_hist)


def check_output(
    output_type: Literal["MessageHistory", "LastMessage"],
    output_model: BaseModel,
):
    if output_model:
        OutputType = output_model  # noqa: N806
    else:
        OutputType = (  # noqa: N806
            MessageHistory if output_type == "MessageHistory" else AssistantMessage
        )

    if (
        output_model and output_type == "MessageHistory"
    ):  # TODO: add support for MessageHistory output type with output_model. Maybe resp.answer = message_hist and resp.structured = model response
        raise NotImplementedError(
            "MessageHistory output type is not supported with output_model at the moment."
        )
    return OutputType
