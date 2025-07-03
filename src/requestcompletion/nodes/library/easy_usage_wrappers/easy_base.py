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
from requestcompletion.nodes.library._llm_base import (
    LLMBase,
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


class EasyBase(LLMBase[_T], ABC, Generic[_T]):
    def __init_subclass__(
        cls,
        pretty_name: str | None = None,
        system_message: SystemMessage | str | None = None,
        model: ModelBase | None = None,
        tool_details: str | None = None,
        tool_params: dict | None = None,
        **kwargs,
    ):
        has_abstract_methods = any(
        getattr(getattr(cls, name, None), '__isabstractmethod__', False)
        for name in dir(cls)
        )

        if not has_abstract_methods:
            validate_tool_metadata(tool_params, tool_details, system_message, pretty_name)
            if system_message is not None and isinstance(
                system_message, str
            ):  # system_message is a string, (tackled at the time of node creation)
                system_message = SystemMessage(system_message)

            # Initialize class wide variables passed by factory function
            cls._pretty_name = pretty_name
            cls._system_message = system_message
            cls._model = model
            cls._tool_details = tool_details
            cls._tool_params = tool_params

        # Now that attributes are set, we can validate the attributes
        super().__init_subclass__(**kwargs)

    def __init__(
        self,
        message_history: MessageHistory,
        llm_model: ModelBase | None = None,
    ):
        check_message_history(
            message_history, self.__class__._system_message
        )  # raises NodeInvocationError if any of the checks fail
        message_history_copy = deepcopy(message_history)
        if self.__class__._system_message is not None:
            if len([x for x in message_history_copy if x.role == Role.system]) > 0:
                warnings.warn(
                    "System message already exists in message history. We will replace it."
                )
                message_history_copy = [
                    x for x in message_history_copy if x.role != Role.system
                ]
                message_history_copy.insert(0, self.__class__._system_message)
            else:
                message_history_copy.insert(0, self.__class__._system_message)

        if llm_model is not None:
            if self.__class__._model is not None:
                warnings.warn(
                    "You have provided a model as a parameter and as a class variable. We will use the parameter."
                )
        else:
            check_model(
                self.__class__._model
            )  # raises NodeInvocationError if any of the checks fail
            llm_model = self.__class__._model

        super().__init__(message_history=message_history_copy, model=llm_model)


    @classmethod
    def tool_info(cls):
        return Tool(
            name=cls.pretty_name().replace(" ", "_"),
            detail=cls._tool_details,
            parameters=cls._tool_params,
        )

    @classmethod
    def prepare_tool(cls, tool_parameters: Dict[str, Any]) -> Self:
        message_hist = MessageHistory(
            [
                UserMessage(f"{cls.param.name}: '{tool_parameters[param.name]}'")
                for param in (cls._tool_params if cls._tool_params else [])
            ]
        )
        return cls(message_hist)



