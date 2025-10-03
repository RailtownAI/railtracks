import asyncio
from typing import Generator

from railtracks.exceptions import LLMError
from railtracks.llm import Message, MessageHistory, ModelBase, UserMessage
from railtracks.llm.response import Response

from ._llm_base import LLMBase, StringOutputMixIn
from .response import StringResponse


class TerminalLLM(
    StringOutputMixIn,
    LLMBase[StringResponse | Generator[str | StringResponse, None, StringResponse]],
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
        result = await rc.call(TerminalLLM, user_input=mh)
        # Using UserMessage
        user_msg = UserMessage("Tell me about the world around us")
        result = await rc.call(TerminalLLM, user_input=user_msg)
        # Using string
        result = await rc.call(
            TerminalLLM, user_input="Tell me about the world around us"
        )
        ```
    """

    def __init__(
        self,
        user_input: MessageHistory | UserMessage | str | list[Message],
        llm: ModelBase | None = None,
    ):
        super().__init__(llm=llm, user_input=user_input)

    @classmethod
    def name(cls) -> str:
        return "Terminal LLM"

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

        if isinstance(returned_mess, Generator):

            def gen_wrapper():
                for r in returned_mess:
                    if isinstance(r, Response):
                        message = r.message

                        self._handle_output(message)
                        string_response = self.return_output(message)
                        yield string_response
                        return string_response
                    elif isinstance(r, str):
                        yield r
                    else:
                        raise LLMError(
                            reason=f"ModelLLM returned unexpected type in generator. Expected str or Response, got {type(r)}",
                            message_history=self.message_hist,
                        )

                raise LLMError(
                    reason="The generator did not yield a final Response object",
                    message_history=self.message_hist,
                )

            return gen_wrapper()
        elif isinstance(returned_mess, Response):
            self._handle_output(returned_mess.message)

            return self.return_output(returned_mess.message)
        else:
            raise LLMError(
                reason="ModelLLM returned an unexpected message type.",
                message_history=self.message_hist,
            )

    def _handle_output(self, output: Message):
        if output.role != "assistant":
            raise LLMError(
                reason="ModelLLM returned an unexpected message type.",
                message_history=self.message_hist,
            )

        if not isinstance(output.content, str):
            raise LLMError(
                reason=f"ModelLLM returned unexpected content. Expected a string, got {type(output.content)}",
                message_history=self.message_hist,
            )

        self.message_hist.append(output)

        return output
