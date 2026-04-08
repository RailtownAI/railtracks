import asyncio

from railtracks.llm import ToolCall, ToolResponse

from ..utils.logging.create import get_rt_logger
from .human_in_the_loop import HIL, HILMessage

logger = get_rt_logger(__name__)


class CliUI(HIL):
    """Terminal-based human-in-the-loop UI implementation.
    
    Provides a simple text-based interface for interactive agent conversations in terminal environments.
    Implements the HIL (Human-in-the-Loop) contract to enable chat-based interaction with LLM agents.
    
    Messages are printed to stdout and user input is read from stdin using blocking input().
    Supports tool invocations, attachments (future), and graceful session termination via 'exit'/'quit'.
    
    Attributes:
        _is_connected: Internal state tracking whether the CLI session is active.
    """

    def __init__(self):
        """Initialize a new CliUI instance.
        
        Sets up the terminal UI with default disconnected state. No server or background tasks
        are spawned—all interaction is synchronous blocking I/O on stdin/stdout.
        """
        self._is_connected = False

    @property
    def is_connected(self) -> bool:
        """Check if the CLI session is currently active.
        
        Returns:
            True if session is connected, False otherwise.
        """
        return self._is_connected

    @is_connected.setter
    def is_connected(self, value: bool) -> None:
        """Set the connection state of the CLI session.
        
        Args:
            value: True to mark session as connected, False to mark as disconnected.
        """
        self._is_connected = value

    async def connect(self) -> None:
        """Initialize and connect the CLI session.
        
        Marks the session as connected and displays a welcome banner on stdout and logs the event.
        Called by the interactive loop before beginning conversation with the agent.
        """
        self._is_connected = True
        logger.info("[railtracks] CLI session started. Type 'exit' to quit.")
        print("[railtracks] CLI session started. Type 'exit' to quit.")

    async def disconnect(self) -> None:
        """Disconnect and close the CLI session.
        
        Marks the session as disconnected and displays a closing message on stdout.
        Called when the user types 'exit'/'quit' or when the interactive loop terminates.
        """
        self._is_connected = False
        logger.info("[railtracks] Session ended.")
        print("[railtracks] Session ended.")

    async def send_message(
        self, content: HILMessage, timeout: float | None = 5.0
    ) -> bool:
        """Display an agent message to the user on stdout.
        
        Prints the agent's response with an 'Agent:' prefix. If not connected, logs a warning
        and returns False without printing.
        
        Args:
            content: The message to send containing the agent's response text.
            timeout: Accepted for interface compatibility but not used (print is non-blocking).
            
        Returns:
            True if the message was displayed successfully, False if disconnected.
        """
        if not self._is_connected:
            logger.warning("Cannot send message - not connected")
            return False

        print(f"Agent: {content.content}")
        logger.debug(f"Message sent: {content.content}")
        return True

    async def receive_message(self, timeout: float | None = None) -> HILMessage | None:
        """Wait for and receive user input from the terminal.
        
        Displays a 'You:' prompt and blocks on stdin waiting for user input. Input is read
        line-by-line until the user presses Enter. Special commands 'exit' and 'quit' trigger
        immediate session disconnection. EOF (Ctrl+D) or KeyboardInterrupt (Ctrl+C) also
        disconnect the session gracefully.
        
        Args:
            timeout: Accepted for interface compatibility but NOT enforced for blocking input().
                     To implement timeout in the future, use signal handlers or asyncio timeouts.
                     
        Returns:
            HILMessage containing the user's input text if successful, None if user exits or
            if the session is not connected.
            
        Note:
            Multimodal file attachments are not yet supported (TODO #826).
        """
        if not self._is_connected:
            return None

        loop = asyncio.get_event_loop()
        try:
            user_input = await loop.run_in_executor(None, input, "You: ")
        except (EOFError, KeyboardInterrupt):
            logger.debug("Received EOF or KeyboardInterrupt")
            await self.disconnect()
            return None

        if user_input.strip().lower() in ("exit", "quit"):
            logger.debug("User typed exit/quit")
            await self.disconnect()
            return None

        # TODO #826: multimodal support — accept file paths as input (attachments)
        logger.debug(f"Received user input: {user_input[:50]}..." if len(user_input) > 50 else f"Received user input: {user_input}")
        return HILMessage(content=user_input)

    async def update_tools(
        self, tool_invocations: list[tuple[ToolCall, ToolResponse]]
    ) -> bool:
        """Display tool invocation results to the user.
        
        Prints each tool call and its result in a compact format: [tool] <name>(<args>) -> <result>.
        Useful for showing the agent's tool usage during conversation. If not connected, logs a
        warning and returns False without printing.
        
        Args:
            tool_invocations: List of (ToolCall, ToolResponse) tuples representing executed tools.
            
        Returns:
            True if all tools were displayed successfully, False if disconnected.
        """
        if not self._is_connected:
            logger.warning("Cannot update tools - not connected")
            return False

        for tool_call, tool_response in tool_invocations:
            args_repr = tool_call.arguments
            result_repr = tool_response.result
            message = f"[tool] {tool_call.name}({args_repr}) -> {result_repr}"
            print(message)
            logger.debug(f"Tool invoked: {tool_call.name}")

        return True
