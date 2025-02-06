from ...llm import MessageHistory, ModelBase, SystemMessage
from ..nodes import Node, ResetException

from abc import ABC, abstractmethod


class TerminalLLM(Node[str], ABC):
    """A simple LLM nodes that takes in a message and returns a response. It is the simplest of all llms."""

    def __init__(self, message_history: MessageHistory):
        """Creates a new instance of the TerminalLLM class

        Args:

        """
        super().__init__()
        self.model = self.create_model()
        assert len(message_history) >= 1, "The message history should include at least one message"
        assert all(
            [m.role != "system" for m in message_history]
        ), "You must not include any system messages in the history"
        self.message_hist = MessageHistory([SystemMessage(self.system_message())])
        self.message_hist += message_history

    @classmethod
    @abstractmethod
    def system_message(cls) -> str: ...

    @classmethod
    @abstractmethod
    def create_model(cls) -> ModelBase: ...

    def invoke(self) -> str:
        """Makes a call containing the inputted message and system prompt to the model and returns the response

        Returns:
            (TerminalLLM.Output): The response message from the model
        """
        try:
            returned_mess = self.model.chat(self.message_hist)
        except Exception as e:
            raise ResetException(node=self, detail=f"{e}")

        self.message_hist.append(returned_mess.message)

        if returned_mess.message.role == "assistant":
            cont = returned_mess.message.content
            if cont is None:
                raise ResetException(node=self, detail="The LLM returned no content")
            return cont

        raise ResetException(
            node=self,
            detail="ModelLLM returned an unexpected message type.",
        )
