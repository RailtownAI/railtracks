from __future__ import annotations

from typing import Callable, List

from .message import Message, Role


class MessageHistory(List[Message]):
    """
    A basic object that represents a history of messages. The object has all the same capability as a list such as
    `.remove()`, `.append()`, etc.
    """

    def __str__(self):
        return "\n".join([str(message) for message in self])

    def removed_system_messages(self) -> MessageHistory:
        """
        Returns a new MessageHistory object with all SystemMessages removed.
        """
        return MessageHistory([msg for msg in self if msg.role != Role.system])
    
    def num_tokens(self, token_function: Callable[[str], int]) -> int:
        return sum(msg.num_tokens(token_function) for msg in self)
