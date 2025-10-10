import asyncio
from abc import ABC
from typing import Generator, Generic, Literal, TypeVar

from pydantic import BaseModel

from railtracks.exceptions.errors import LLMError
from railtracks.llm import Message, MessageHistory, ModelBase, UserMessage
from railtracks.validation.node_creation.validation import (
    check_classmethod,
    check_schema,
)

from ._llm_base import LLMBase, StructuredOutputMixIn
from .response import StructuredResponse

_TOutput = TypeVar("_TOutput", bound=StructuredResponse)
_TStream = TypeVar("_TStream", Literal[True], Literal[False])
_T = TypeVar("_T")
_TBaseModel = TypeVar("_TBaseModel", bound=BaseModel)


class StructuredLLMBase(
    StructuredOutputMixIn[_TBaseModel],
    LLMBase[_T, StructuredResponse[_TBaseModel], _TStream],
    ABC,
    Generic[_T, _TStream, _TBaseModel],
):
    """
    Python typing doesn't work great, so please ensure that you fit the following requirements when defining generics:
    - _T is the final output type of the invoke method
    - _TStream is a Literal type, either Literal[True] or Literal[False]
    - _TBaseModel is a subclass of pydantic.BaseModel that defines the schema for the structured output

    """

    def __init_subclass__(cls):
        super().__init_subclass__()
        if "output_schema" in cls.__dict__ and not getattr(
            cls, "__abstractmethods__", False
        ):
            method = cls.__dict__["output_schema"]
            check_classmethod(method, "output_schema")
            check_schema(method, cls)

    def __init__(
        self,
        user_input: MessageHistory | UserMessage | str | list[Message],
        llm: ModelBase[_TStream] | None = None,
    ):
        super().__init__(llm=llm, user_input=user_input)

    @classmethod
    def name(cls) -> str:
        return f"Structured LLM ({cls.output_schema().__name__})"

    def _handle_output(self, output: Message):
        if not isinstance(output.content, self.output_schema()):
            raise LLMError(
                f"Output from LLM is not of the correct type. Got {type(output.content)} instead of {self.output_schema()}."
            )
        super()._handle_output(output)


class StructuredLLM(
    StructuredLLMBase[StructuredResponse[_TBaseModel], Literal[False], _TBaseModel],
    ABC,
    Generic[_TBaseModel],
):
    """Creates a new instance of the StructuredlLLM class

    Args:
        user_input (MessageHistory | UserMessage | str | list[Message]): The input to use for the LLM. Can be a MessageHistory object, a UserMessage object, or a string.
            If a string is provided, it will be converted to a MessageHistory with a UserMessage.
            If a UserMessage is provided, it will be converted to a MessageHistory.
        llm_model (ModelBase | None, optional): The LLM model to use. Defaults to None.

    """

    # TODO: allow for more general (non-pydantic) outputs

    async def invoke(self):
        """Makes a call containing the inputted message and system prompt to the llm model and returns the response

        Returns:
            (StructuredlLLM.Output): The response message from the llm model
        """

        returned_mess = await asyncio.to_thread(
            self.llm_model.structured, self.message_hist, schema=self.output_schema()
        )

        self._handle_output(returned_mess.message)
        return self.return_output(returned_mess.message)


class StreamingStructuredLLM(
    StructuredLLMBase[
        Generator[
            StructuredResponse[_TBaseModel] | str, None, StructuredResponse[_TBaseModel]
        ],
        Literal[True],
        _TBaseModel,
    ],
    ABC,
    Generic[_TBaseModel],
):
    """A simple streaming LLM node that takes in a message and returns a response. It is the simplest of all LLMs.
    This node accepts message_history in the following formats:
    - MessageHistory: A list of Message objects
    - UserMessage: A single UserMessage object
    - str: A string that will be converted to a UserMessage

    Examples:
        ```python
        # Using MessageHistory
        mh = MessageHistory([UserMessage("Tell me about the world around us")])
        result = await rt.call(StreamingStructuredLLM, user_input=mh)
        # Using UserMessage
        user_msg = UserMessage("Tell me about the world around us")
        result = await rt.call(StreamingStructuredLLM, user_input=user_msg)
        # Using string
        result = await rt.call(
            StreamingStructuredLLM, user_input="Tell me about the world around us"
        )
        ```
    """

    async def invoke(self):
        """Makes a call containing the inputted message and system prompt to the llm model and returns the response

        Returns:
            (StructuredlLLM.Output): The response message from the llm model
        """

        returned_mess = await asyncio.to_thread(
            self.llm_model.structured, self.message_hist, schema=self.output_schema()
        )

        return self._gen_wrapper(returned_mess)
