from ...exceptions import LLMError
from ...llm import MessageHistory, ModelBase
from ._llm_base import LLMBase


class TerminalLLM(LLMBase[str]):
    """A simple LLM nodes that takes in a message and returns a response. It is the simplest of all llms."""

    def __init__(
        self, message_history: MessageHistory, llm_model: ModelBase | None = None
    ):
        """Creates a new instance of the TerminalLLM class

        Args:

        """
        super().__init__(llm_model=llm_model, message_history=message_history)

    @classmethod
    def pretty_name(cls) -> str:
        return "TerminalLLM"

    async def invoke(self) -> str | None:
        """Makes a call containing the inputted message and system prompt to the llm model and returns the response

        Returns:
            (TerminalLLM.Output): The response message from the llm model
        """
        try:
            returned_mess = await self.llm_model.achat(self.message_hist)
        except Exception as e:
            raise LLMError(
                reason=f"Exception during llm model chat: {str(e)}",
                message_history=self.message_hist,
            )

        self.message_hist.append(returned_mess.message)
        if returned_mess.message.role == "assistant":
            cont = returned_mess.message.content
            if cont is None:
                raise LLMError(
                    reason="ModelLLM returned None content",
                    message_history=self.message_hist,
                )
            return cont

        raise LLMError(
            reason="ModelLLM returned an unexpected message type.",
            message_history=self.message_hist,
        )
