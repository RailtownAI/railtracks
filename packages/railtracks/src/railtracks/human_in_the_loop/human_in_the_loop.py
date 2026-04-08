from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from pydantic import BaseModel, model_validator


class UserMessageAttachment(BaseModel):
    type: str  # "file" or "url"
    url: Optional[str] = None
    data: Optional[str] = None
    name: Optional[str] = None

    @model_validator(mode="after")
    def validate_attachment(self) -> "UserMessageAttachment":
        if self.url is None and self.data is None:
            raise ValueError("Either 'url' or 'data' must be provided.")
        return self


class HILMessage(BaseModel):
    content: str
    metadata: Dict[str, Any] | None = None
    attachments: Optional[list[UserMessageAttachment]] = None


class HIL(ABC):
    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Returns True when the interface is currently connected."""
        pass

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

    @abstractmethod
    async def update_tools(self, tool_invocations: list[Any]) -> bool:
        """Sends tool invocation information to the UI."""
        pass
