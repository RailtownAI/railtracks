import railtracks.context as context
from railtracks.exceptions import LLMError
from railtracks.llm import Message, MessageHistory, ModelBase, UserMessage

from ._llm_base import LLMBase, StringOutputMixIn
from .response import StringResponse
from railtracks.llm.content import Stream

class TerminalLLM(StringOutputMixIn, LLMBase[StringResponse]):
    def __init__(
        self,
        user_input: MessageHistory | UserMessage | str | list[Message],
        llm_model: ModelBase | None = None,
    ):
        super().__init__(llm_model=llm_model, user_input=user_input)

    @classmethod
    def name(cls) -> str:
        return "Terminal LLM"

    async def invoke(self) -> StringResponse:
        try:
            returned_mess = self.llm_model.chat(self.message_hist)
        except Exception as e:
            raise LLMError(
                reason=f"Exception during llm model chat: {str(e)}",
                message_history=self.message_hist,
            )
        assert returned_mess.message
        if returned_mess.message.role == "assistant":
            cont = returned_mess.message.content
            if isinstance(cont, Stream):    # if the AssistantMessage is a stream, we need to add the final message to the message history instead of the generator
                assert isinstance(cont.final_message, str), "The _post_llm_hook should have ensured that the final message is populated"
                returned_mess.message._content = cont.final_message
            elif cont is None:
                raise LLMError(
                    reason="ModelLLM returned None content",
                    message_history=self.message_hist,
                )
            self.message_hist.append(returned_mess.message)
            return self.return_output(returned_mess.message)

        raise LLMError(
            reason="ModelLLM returned an unexpected message type.",
            message_history=self.message_hist,
        )