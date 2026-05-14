from abc import ABC, abstractmethod
from collections.abc import Callable


from railtracks.llm.history import MessageHistory
from railtracks.nodes.nodes import Node


class ContextCompression(ABC):
    """Any subclasses should add to a previous history every time it does a compression. """
    def __init__(self, max_tokens: int):
        self.previous_histories: list[MessageHistory] = []
        self.max_tokens = max_tokens

    async def run(self, message_history: MessageHistory, token_counter: Callable[[str], int]) -> MessageHistory:
        if message_history.num_tokens(token_counter) <= self.max_tokens:
            return message_history
        compressed_history = await self._compress(message_history, token_counter)
        self.previous_histories.append(message_history)
        return compressed_history

    @abstractmethod
    async def _compress(self, message_history: MessageHistory, token_counter: Callable[[str], int]) -> MessageHistory:
        """
        Compresses the context of the node and returns a new MessageHistory object that can be used in place of the original context.
        """
        pass

