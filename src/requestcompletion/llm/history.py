from typing import List

from .message import Message


class MessageHistory(List[Message]):
    def is_valid(self):
        """
        Checks if the message history is valid.

        Returns:
            True if the message history is valid, False otherwise.

        """
        return True

    def __str__(self):
        return "\n".join([str(message) for message in self])
