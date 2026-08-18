###
# In the following document, we will use the interface types defined in this module to interact with the llama index to
# route to a given model.
###
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import (
    AsyncGenerator,
    List,
    Type,
)
from uuid import uuid4

from pydantic import BaseModel

from .history import MessageHistory
from .providers import ModelProvider
from .response import Response
from .retries.base import RetryApproach
from .tools import Tool


class ModelBase(ABC):
    """
    A simple base that represents the behavior of a model that can be used for chat, structured interactions, and streaming.
    """

    def __init__(
        self,
        retry_approach: RetryApproach | None = None,
    ):
        self.retry_approach = retry_approach
        self.id = str(uuid4())

    @abstractmethod
    def model_name(self) -> str:
        """
        Returns the name of the model being used.

        It can be treated as unique identifier for the model when paired with the `model_type`.
        """
        pass

    @abstractmethod
    def model_provider(self) -> ModelProvider:
        """The name of the provider of this model (The Company that owns the model)"""
        pass

    @classmethod
    @abstractmethod
    def model_gateway(cls) -> ModelProvider:
        """
        Gets the API distrubutor of the model. Note nessecarily the same as the model itself.

        E.g. if you are calling openai LLM through Azure AI foundry
        """
        pass

    def chat(self, messages: MessageHistory) -> Response:
        """Chat with the model using the provided messages."""
        return self._chat(messages)

    async def achat(self, messages: MessageHistory) -> Response:
        """Asynchronous chat with the model using the provided messages."""
        return await self._achat(messages)

    def structured(self, messages: MessageHistory, schema: Type[BaseModel]) -> Response:
        """Structured interaction with the model using the provided messages and output_schema."""
        return self._structured(messages, schema)

    async def astructured(
        self, messages: MessageHistory, schema: Type[BaseModel]
    ) -> Response:
        """Asynchronous structured interaction with the model using the provided messages and output_schema."""
        return await self._astructured(messages, schema)

    def chat_with_tools(self, messages: MessageHistory, tools: List[Tool]) -> Response:
        """Chat with the model using the provided messages and tools."""
        return self._chat_with_tools(messages, tools)

    async def achat_with_tools(
        self, messages: MessageHistory, tools: List[Tool]
    ) -> Response:
        """Asynchronous chat with the model using the provided messages and tools."""
        return await self._achat_with_tools(messages, tools)

    # ================ START Streaming (per-call) LLM calls ===============
    # These methods request a streamed response for a single call. They are the model-level
    # building blocks of railtracks streaming (see `rt.astream` at the framework level).

    async def astream_chat(
        self, messages: MessageHistory
    ) -> AsyncGenerator[str | Response, None]:
        """
        Chat with the model, streaming the response.

        Returns an async generator that yields `str` token chunks as they arrive, followed by a
        single final `Response` object containing the complete message (and usage info).

        ```python
        async for item in model.astream_chat(MessageHistory([UserMessage("hi")])):
            if isinstance(item, str):
                ...  # token chunk
            else:
                final = item  # the terminal Response
        ```

        Args:
            messages: The conversation so far, as a `MessageHistory`.

        Yields:
            str | Response: `str` token chunks, then one final complete `Response`.
        """
        async for item in self._astream_chat(messages):
            yield item

    async def astream_chat_with_tools(
        self, messages: MessageHistory, tools: List[Tool]
    ) -> AsyncGenerator[str | Response, None]:
        """
        Chat with the model using tools, streaming the response.

        Yields `str` content chunks as they arrive, followed by a single final `Response`. The
        final `Response` contains either the complete assistant text or the requested tool
        calls (tool-call deltas are accumulated internally and are not yielded as chunks).

        Args:
            messages: The conversation so far, as a `MessageHistory`.
            tools: The tools to make available to the model.

        Yields:
            str | Response: `str` content chunks, then one final complete `Response`.
        """
        async for item in self._astream_chat_with_tools(messages, tools):
            yield item

    async def astream_structured(
        self, messages: MessageHistory, schema: Type[BaseModel]
    ) -> AsyncGenerator[str | Response, None]:
        """
        Structured interaction with the model, streaming the response.

        Yields the raw (JSON) `str` chunks as they arrive, followed by a single final
        `Response` whose message content is the parsed `schema` instance.

        Note the chunks are unvalidated JSON fragments; validation only happens once the stream
        completes, so a schema mismatch surfaces at the end of the stream.

        Args:
            messages: The conversation so far, as a `MessageHistory`.
            schema: The pydantic model the response must conform to.

        Yields:
            str | Response: raw JSON `str` chunks, then one final complete `Response`.
        """
        async for item in self._astream_structured(messages, schema):
            yield item

    # ================ END Streaming (per-call) LLM calls ===============

    @abstractmethod
    def _chat(self, messages: MessageHistory) -> Response:
        pass

    @abstractmethod
    def _structured(
        self, messages: MessageHistory, schema: Type[BaseModel]
    ) -> Response:
        pass

    @abstractmethod
    def _chat_with_tools(self, messages: MessageHistory, tools: List[Tool]) -> Response:
        pass

    # Note: the _astream_* methods are deliberately NOT abstract so that existing ModelBase
    # subclasses keep working; subclasses that support streaming should override them with
    # async generator implementations yielding `str` chunks followed by a final `Response`.

    def _astream_chat(
        self, messages: MessageHistory
    ) -> AsyncGenerator[str | Response, None]:
        raise NotImplementedError(
            f"{type(self).__name__} does not support streamed chat calls."
        )

    def _astream_chat_with_tools(
        self, messages: MessageHistory, tools: List[Tool]
    ) -> AsyncGenerator[str | Response, None]:
        raise NotImplementedError(
            f"{type(self).__name__} does not support streamed tool-calling calls."
        )

    def _astream_structured(
        self, messages: MessageHistory, schema: Type[BaseModel]
    ) -> AsyncGenerator[str | Response, None]:
        raise NotImplementedError(
            f"{type(self).__name__} does not support streamed structured calls."
        )

    @abstractmethod
    async def _achat(self, messages: MessageHistory) -> Response:
        pass

    @abstractmethod
    async def _astructured(
        self,
        messages: MessageHistory,
        schema: Type[BaseModel],
    ) -> Response:
        pass

    @abstractmethod
    async def _achat_with_tools(
        self, messages: MessageHistory, tools: List[Tool]
    ) -> Response:
        pass
