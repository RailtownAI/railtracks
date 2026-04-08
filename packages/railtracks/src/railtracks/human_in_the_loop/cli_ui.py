import asyncio

from railtracks.llm import ToolCall, ToolResponse

from ..utils.logging.create import get_rt_logger
from .human_in_the_loop import HIL, HILMessage

logger = get_rt_logger(__name__)


class CliUI(HIL):
    """Terminal-based human-in-the-loop UI implementation."""

    def __init__(self):
        self._is_connected = False

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    async def connect(self) -> None:
        self._is_connected = True
        print("[railtracks] CLI session started. Type 'exit' to quit.")

    async def disconnect(self) -> None:
        self._is_connected = False
        print("[railtracks] Session ended.")

    async def send_message(
        self, content: HILMessage, timeout: float | None = 5.0
    ) -> bool:
        if not self._is_connected:
            logger.warning("Cannot send message - not connected")
            return False

        print(f"Agent: {content.content}")
        return True

    async def receive_message(self, timeout: float | None = None) -> HILMessage | None:
        if not self._is_connected:
            return None

        loop = asyncio.get_event_loop()
        try:
            user_input = await loop.run_in_executor(None, input, "You: ")
        except (EOFError, KeyboardInterrupt):
            await self.disconnect()
            return None

        if user_input.strip().lower() in ("exit", "quit"):
            await self.disconnect()
            return None

        # TODO #826: multimodal support — accept file paths as input (attachments)
        return HILMessage(content=user_input)

    async def update_tools(
        self, tool_invocations: list[tuple[ToolCall, ToolResponse]]
    ) -> bool:
        if not self._is_connected:
            logger.warning("Cannot update tools - not connected")
            return False

        for tool_call, tool_response in tool_invocations:
            args_repr = tool_call.arguments
            result_repr = tool_response.result
            print(f"[tool] {tool_call.name}({args_repr}) -> {result_repr}")

        return True
