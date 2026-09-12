from __future__ import annotations

from typing import List

from .message import Message, Role, _AgentSystemMessage


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

    def without_agent_system_messages(self) -> MessageHistory:
        """
        Returns a new MessageHistory object with the agent's own SystemMessage removed.

        SystemMessages the caller placed in the history are kept, so the result can be handed
        straight back to an agent for the next turn without losing the prompt it was given.
        """
        return MessageHistory(
            [msg for msg in self if not isinstance(msg, _AgentSystemMessage)]
        )
