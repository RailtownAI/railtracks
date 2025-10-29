from abc import ABC, abstractmethod
from typing import Any, Dict

from pydantic import BaseModel


class HILMessage(BaseModel):
    content: str
    metadata: Dict[str, Any] | None = None


class HIL(ABC):
    @abstractmethod
    async def connect(self) -> None:
        """
        Creates or initializes the user interface component.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """
        Disconnects the user interface component.
        """
        pass

    @abstractmethod
    async def send_message(
        self, content: HILMessage, timeout: float | None = None
    ) -> bool:
        """
        HIL uses this function to send a message to the user through the interface.

        Args:
            content: The message content to send.
            timeout: The maximum time in seconds to wait for the message to be sent.

        Returns:
            True if the message was sent successfully, False otherwise.
        """
        pass

    @abstractmethod
    async def receive_message(self, timeout: float | None = None) -> HILMessage | None:
        """
        HIL uses this function to wait for the user to provide input.

        This method should block until input is received or the timeout is reached.

        Args:
            timeout: The maximum time in seconds to wait for input.

        Returns:
            The user input if received within the timeout period, None otherwise.
        """
        pass
