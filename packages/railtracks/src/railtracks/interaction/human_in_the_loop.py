from abc import ABC, abstractmethod

class HIL(ABC):
    @abstractmethod
    def connect(self) -> bool:
        """
        Connects to an existing user interface or starts a new one if none exists.

        Returns:
            True if the connection was successful, False otherwise.
        """
        pass
    
    @abstractmethod
    async def send_message(self, content: str, timeout: float | None) -> bool:
        """
        Sends a message to the user through the interface.

        Args:
            content: The message content to send.

        Returns:
            True if the message was sent successfully, False otherwise.
        """
        pass

    @abstractmethod
    async def wait_for_user_input(self, timeout: float | None) -> bool:
        """
        Waits for user input from the user interface.
        
        Args:
            timeout: The maximum time in seconds to wait for input.

        Returns:
            True if input was received within the timeout period, False otherwise.
        """
        pass
