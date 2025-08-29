from railtracks.exceptions import LLMError
from railtracks.llm import Message, MessageHistory, ModelBase, UserMessage
from railtracks.llm.content import Stream

from ._llm_base import LLMBase, StringOutputMixIn
from .response import StringResponse


class TerminalLLM(StringOutputMixIn, LLMBase[StringResponse]):
    def __init__(
        self,
        user_input: MessageHistory | UserMessage | str | list[Message],
        llm: ModelBase | None = None,
    ):
        super().__init__(llm=llm, user_input=user_input)

    @classmethod
    def name(cls) -> str:
        return "Terminal LLM"

    async def invoke(self) -> StringResponse:
        try:
            returned_mess = await self.llm_model.achat(self.message_hist)
        except Exception as e:
            raise LLMError(
                reason=f"Exception during llm model chat: {str(e)}",
                message_history=self.message_hist,
            )
        assert returned_mess.message
        if returned_mess.message.role == "assistant":
            cont = returned_mess.message.content
            if isinstance(
                cont, Stream
            ):  # if the AssistantMessage is a stream, we need to add the final message to the message history instead of the generator
                assert isinstance(cont.final_message, str), (
                    "The _stream_handler_base in _litellm_wrapper should have ensured that the final message is populated"
                )
                self.message_hist.append(
                    Message(content=cont.final_message, role="assistant")
                )  # instead of the generator we attach the final_message to the message history
            elif isinstance(cont, str):
                self.message_hist.append(returned_mess.message)
            else:
                raise LLMError(
                    reason=f"ModelLLM returned unexpected content. Expected a string or stream, got {type(cont)}",
                    message_history=self.message_hist,
                )
            return self.return_output(returned_mess.message)

        raise LLMError(
            reason="ModelLLM returned an unexpected message type.",
            message_history=self.message_hist,
        )
