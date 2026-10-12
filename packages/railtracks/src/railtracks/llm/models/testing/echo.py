"""Offline echo model for tests that must not call a provider."""

from __future__ import annotations

from typing import List, Type

from pydantic import BaseModel

from ...history import MessageHistory
from ...message import AssistantMessage
from ...model import ModelBase
from ...providers import ModelProvider
from ...response import MessageInfo, Response
from ...tools import Tool

_ECHO_LINE = "This is an echo of the test model."


class EchoLLM(ModelBase):
    """Offline model that returns the message history it was given.

    Each chat call returns one assistant message. The text is every received
    message, in order, one per line in its ``str()`` form (``role: content``),
    followed by ``This is an echo of the test model.`` The model never requests
    a tool call. ``structured`` and ``astructured`` raise
    ``NotImplementedError``.

    Creating or calling this model does not need an API key or network access.
    The reported usage is zero tokens, zero cost, and zero latency, and the
    model name is ``echo``.
    """

    def model_name(self) -> str:
        """Return ``"echo"``.

        Returns:
            str: The name ``"echo"``.
        """
        return "echo"

    def model_provider(self) -> ModelProvider:
        """Return `ModelProvider.UNKNOWN`.

        The echo model is not served by a provider.

        Returns:
            ModelProvider: `ModelProvider.UNKNOWN`.
        """
        return ModelProvider.UNKNOWN

    @classmethod
    def model_gateway(cls) -> ModelProvider:
        """Return `ModelProvider.UNKNOWN`.

        The echo model is not reached through a gateway.

        Returns:
            ModelProvider: `ModelProvider.UNKNOWN`.
        """
        return ModelProvider.UNKNOWN

    def _message_info(self) -> MessageInfo:
        return MessageInfo(
            input_tokens=0,
            output_tokens=0,
            latency=0.0,
            model_name=self.model_name(),
            total_cost=0.0,
        )

    def _echo(self, messages: MessageHistory) -> Response:
        lines = [str(message) for message in messages]
        lines.append(_ECHO_LINE)
        return Response(
            message=AssistantMessage("\n".join(lines)),
            message_info=self._message_info(),
        )

    def _chat(self, messages: MessageHistory) -> Response:
        """Return the echoed history as an assistant message.

        Args:
            messages: The conversation the caller sent.

        Returns:
            Response: One assistant message containing the compacted history.
        """
        return self._echo(messages)

    def _chat_with_tools(self, messages: MessageHistory, tools: List[Tool]) -> Response:
        """Return the echoed history and do not request a tool call.

        Args:
            messages: The conversation the caller sent.
            tools: Tools offered to the model. None of them is requested.

        Returns:
            Response: The same echo `_chat` returns for `messages`.
        """
        return self._echo(messages)

    def _structured(
        self, messages: MessageHistory, schema: Type[BaseModel]
    ) -> Response:
        """Reject structured output.

        Args:
            messages: The conversation the caller sent.
            schema: The pydantic model requested for the response.

        Raises:
            NotImplementedError: EchoLLM does not support structured output.
        """
        raise NotImplementedError("EchoLLM does not support structured output.")

    async def _achat(self, messages: MessageHistory) -> Response:
        """Asynchronous form of `_chat`.

        Args:
            messages: The conversation the caller sent.

        Returns:
            Response: The same response `_chat` returns.
        """
        return self._chat(messages)

    async def _achat_with_tools(
        self, messages: MessageHistory, tools: List[Tool]
    ) -> Response:
        """Asynchronous form of `_chat_with_tools`.

        Args:
            messages: The conversation the caller sent.
            tools: Tools offered to the model. None of them is requested.

        Returns:
            Response: The same response `_chat_with_tools` returns.
        """
        return self._chat_with_tools(messages, tools)

    async def _astructured(
        self, messages: MessageHistory, schema: Type[BaseModel]
    ) -> Response:
        """Asynchronous form of `_structured`.

        Args:
            messages: The conversation the caller sent.
            schema: The pydantic model requested for the response.

        Raises:
            NotImplementedError: EchoLLM does not support structured output.
        """
        return self._structured(messages, schema)
