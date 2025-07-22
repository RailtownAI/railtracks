from ... import context
from ...exceptions import LLMError
from ...llm import MessageHistory, ModelBase, UserMessage
from ._llm_base import LLMBase


class TerminalLLM(LLMBase[str]):
    """A simple LLM node that takes in a message and returns a response. It is the simplest of all LLMs.

    This node accepts message_history in the following formats:
    - MessageHistory: A list of Message objects
    - UserMessage: A single UserMessage object
    - str: A string that will be converted to a UserMessage

    Examples:
        ```python
        # Using MessageHistory
        mh = MessageHistory([UserMessage("Tell me about the world around us")])
        result = await rc.call(TerminalLLM, message_history=mh)

        # Using UserMessage
        user_msg = UserMessage("Tell me about the world around us")
        result = await rc.call(TerminalLLM, message_history=user_msg)

        # Using string
        result = await rc.call(TerminalLLM, "Tell me about the world around us")
        ```
    """

    def __init__(
        self,
        user_input: MessageHistory | UserMessage | str,
        llm_model: ModelBase | None = None,
    ):
        """Creates a new instance of the TerminalLLM class.

        Args:
            user_input: The message history to use. Can be a MessageHistory object, a UserMessage object, or a string.
                If a string is provided, it will be converted to a MessageHistory with a UserMessage.
                If a UserMessage is provided, it will be converted to a MessageHistory.
            llm_model: The LLM model to use. If None, the default model will be used.
        """
        super().__init__(llm_model=llm_model, user_input=user_input)

    @classmethod
    def pretty_name(cls) -> str:
        return "Terminal LLM"

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
            if (key := self.return_into()) is not None:
                context.put(key, self.format_for_context(cont))
                return self.format_for_return(cont)
            return cont

        raise LLMError(
            reason="ModelLLM returned an unexpected message type.",
            message_history=self.message_hist,
        )
