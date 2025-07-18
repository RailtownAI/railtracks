from typing import List

from .message import Message


class MessageHistory(List[Message]):
    """
    A basic object that represents a history of messages. The object has all the same capability as a list such as
    `.remove()`, `.append()`, etc.
    """

    def __str__(self):
        return "\n".join([str(message) for message in self])
