from __future__ import annotations

import asyncio
from abc import ABC
from typing import Generator, Generic, Literal, TypeVar

from railtracks.exceptions import LLMError
from railtracks.llm.response import Response

from ._llm_base import LLMBase, StringOutputMixIn
from .response import LLMResponse, StringResponse

_T = TypeVar(
    "_T", Generator[str | StringResponse, None, StringResponse], StringResponse
)
_TStream = TypeVar("_TStream", Literal[True], Literal[False])
_TCollectedOutput = TypeVar("_TCollectedOutput", bound=LLMResponse)


class TerminalLLMBase(
    LLMBase[_T, _TCollectedOutput, _TStream],
    ABC,
    Generic[_T, _TCollectedOutput, _TStream],
):
    @classmethod
    def name(cls) -> str:
        return "Terminal LLM"


class TerminalLLM(
    StringOutputMixIn,
    TerminalLLMBase[StringResponse, StringResponse, Literal[False]],
):
    """A simple LLM node that takes in a message and returns a response. It is the simplest of all LLMs.
    This node accepts message_history in the following formats:
    - MessageHistory: A list of Message objects
    - UserMessage: A single UserMessage object
    - str: A string that will be converted to a UserMessage
    Examples:
        ```python
        # Using MessageHistory
        mh = MessageHistory([UserMessage("Tell me about the world around us")])
        result = await rt.call(TerminalLLM, user_input=mh)
        # Using UserMessage
        user_msg = UserMessage("Tell me about the world around us")
        result = await rt.call(TerminalLLM, user_input=user_msg)
        # Using string
        result = await rt.call(
            TerminalLLM, user_input="Tell me about the world around us"
        )
        ```
    """

    async def invoke(self):
        """Makes a call containing the inputted message and system prompt to the llm model and returns the response
        Returns:
            (TerminalLLM.Output): The response message from the llm model
        """
        try:
            returned_mess = await asyncio.to_thread(
                self.llm_model.chat, self.message_hist
            )
        except Exception as e:
            raise LLMError(
                reason=f"Exception during llm model chat: {str(e)}",
                message_history=self.message_hist,
            )

        if isinstance(returned_mess, Response):
            self._handle_output(returned_mess.message)

            return self.return_output(returned_mess.message)
        else:
            raise LLMError(
                reason="ModelLLM returned an unexpected message type.",
                message_history=self.message_hist,
            )


class StreamingTerminalLLM(
    StringOutputMixIn,
    TerminalLLMBase[
        Generator[str | StringResponse, None, StringResponse],
        StringResponse,
        Literal[True],
    ],
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
        result = await rt.call(StreamingTerminalLLM, user_input=mh)
        # Using UserMessage
        user_msg = UserMessage("Tell me about the world around us")
        result = await rt.call(StreamingTerminalLLM, user_input=user_msg)
        # Using string
        result = await rt.call(
            StreamingTerminalLLM, user_input="Tell me about the world around us"
        )
        ```
    """

    async def invoke(self):
        """Makes a call containing the inputted message and system prompt to the llm model and returns the response
        Returns:
            (TerminalLLM.Output): The response message from the llm model
        """
        try:
            returned_mess = await asyncio.to_thread(
                self.llm_model.chat, self.message_hist
            )
        except Exception as e:
            raise LLMError(
                reason=f"Exception during llm model chat: {str(e)}",
                message_history=self.message_hist,
            )

        return self._gen_wrapper(returned_mess)
