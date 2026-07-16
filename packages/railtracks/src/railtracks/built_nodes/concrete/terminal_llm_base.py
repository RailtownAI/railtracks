from __future__ import annotations

import asyncio
from abc import ABC

from railtracks.exceptions import LLMError
from railtracks.llm.response import Response

from ._llm_base import LLMBase, StringOutputMixIn
from .response import StringResponse


class TerminalLLMBase(
    LLMBase[StringResponse],
    ABC,
):
    @classmethod
    def name(cls) -> str:
        return "Terminal LLM"


class TerminalLLM(
    StringOutputMixIn,
    TerminalLLMBase,
):
    """A simple LLM node that takes in a message and returns a response. It is the simplest of all LLMs.
    This node accepts message_history in the following formats:
    - MessageHistory: A list of Message objects
    - UserMessage: A single UserMessage object
    - str: A string that will be converted to a UserMessage

    Streaming: when invoked through `rt.astream` (or with a `stream_callback` configured), this
    node streams the model response token-by-token — each chunk is broadcast on the node's
    `stream_channel` — and still returns the complete `StringResponse` at the end. In a regular
    `rt.call` the model is invoked buffered (no streaming overhead).

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
        # Streaming the tokens of the response
        async for chunk in (stream := rt.astream(TerminalLLM, user_input="Tell me a story")):
            print(chunk, end="", flush=True)
        result = stream.result
        ```
    """

    async def invoke(self):
        """Makes a call containing the inputted message and system prompt to the llm model and returns the response
        Returns:
            (TerminalLLM.Output): The response message from the llm model
        """
        context = self._pre_invoke(self.message_hist)
        self.message_hist = context

        try:
            if self._should_stream():
                returned_mess = await self._stream_model_response(
                    self.llm_model.astream_chat(self.message_hist)
                )
            else:
                returned_mess = await asyncio.to_thread(self._buffered_chat)
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(
                reason=f"Exception during llm model chat: {str(e)}",
                message_history=self.message_hist,
            ) from e

        returned_mess = self._post_invoke(self.message_hist, returned_mess)

        if isinstance(returned_mess, Response):
            self._handle_output(returned_mess.message)

            return self.return_output(returned_mess.message)
        else:
            raise LLMError(
                reason="ModelLLM returned an unexpected message type.",
                message_history=self.message_hist,
            )

    def _buffered_chat(self) -> Response:
        """Runs a regular (non-streaming) chat call, draining legacy stream=True generators."""
        return self._collect_streamed_response(self.llm_model.chat(self.message_hist))
