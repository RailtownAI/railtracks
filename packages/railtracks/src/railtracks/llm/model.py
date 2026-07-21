###
# In the following document, we will use the interface types defined in this module to interact with the llama index to
# route to a given model.
###
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import (
    AsyncGenerator,
    Callable,
    List,
    Type,
)

from pydantic import BaseModel

from .history import MessageHistory
from .providers import ModelProvider
from .response import Response
from .retries.base import RetryApproach
from .tools import Tool


class ModelBase(ABC):
    """
    A simple base that represents the behavior of a model that can be used for chat, structured interactions, and streaming.

    The base class allows for the insertion of hooks that can modify the messages before they are sent to the model,
    response after they are received, and map exceptions that may occur during the interaction.

    All the hooks are optional and can be added or removed as needed.
    """

    def __init__(
        self,
        __pre_hooks: List[Callable[[MessageHistory], MessageHistory]] | None = None,
        __post_hooks: List[Callable[[MessageHistory, Response], Response]]
        | None = None,
        __exception_hooks: List[Callable[[MessageHistory, Exception], None]]
        | None = None,
        retry_approach: RetryApproach | None = None,
    ):
        if __pre_hooks is None:
            pre_hooks: List[Callable[[MessageHistory], MessageHistory]] = []
        else:
            pre_hooks = __pre_hooks

        if __post_hooks is None:
            post_hooks: List[Callable[[MessageHistory, Response], Response]] = []
        else:
            post_hooks = __post_hooks

        if __exception_hooks is None:
            exception_hooks: List[Callable[[MessageHistory, Exception], None]] = []
        else:
            exception_hooks = __exception_hooks

        self._pre_hooks = pre_hooks
        self._post_hooks = post_hooks
        self._exception_hooks = exception_hooks
        self.retry_approach = retry_approach

    def add_pre_hook(self, hook: Callable[[MessageHistory], MessageHistory]) -> None:
        """Adds a pre-hook to modify messages before sending them to the model."""
        self._pre_hooks.append(hook)

    def add_post_hook(
        self, hook: Callable[[MessageHistory, Response], Response]
    ) -> None:
        """Adds a post-hook to modify the response after receiving it from the model."""
        self._post_hooks.append(hook)

    def add_exception_hook(
        self, hook: Callable[[MessageHistory, Exception], None]
    ) -> None:
        """Adds an exception hook to handle exceptions during model interactions."""
        self._exception_hooks.append(hook)

    def remove_pre_hooks(self) -> None:
        """Removes all of the hooks that modify messages before sending them to the model."""
        self._pre_hooks = []

    def remove_post_hooks(self) -> None:
        """Removes all of the hooks that modify the response after receiving it from the model."""
        self._post_hooks = []

    def remove_exception_hooks(self) -> None:
        """Removes all of the hooks that handle exceptions during model interactions."""
        self._exception_hooks = []

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

    def _run_pre_hooks(self, message_history: MessageHistory) -> MessageHistory:
        """Runs all pre-hooks on the provided message history."""
        for hook in self._pre_hooks:
            message_history = hook(message_history)
        return message_history

    def _run_post_hooks(
        self, message_history: MessageHistory, result: Response
    ) -> Response:
        """Runs all post-hooks on the provided message history and result."""
        for hook in self._post_hooks:
            result = hook(message_history, result)
        return result

    def _run_exception_hooks(
        self, message_history: MessageHistory, exception: Exception
    ) -> None:
        """Runs all exception hooks on the provided message history and exception."""
        for hook in self._exception_hooks:
            hook(message_history, exception)

    def chat(self, messages: MessageHistory) -> Response:
        """Chat with the model using the provided messages."""
        messages = self._run_pre_hooks(messages)

        try:
            response = self._chat(messages)
        except Exception as e:
            self._run_exception_hooks(messages, e)
            raise e

        return self._run_post_hooks(messages, response)

    async def achat(self, messages: MessageHistory) -> Response:
        """Asynchronous chat with the model using the provided messages."""
        messages = self._run_pre_hooks(messages)

        try:
            response = await self._achat(messages)
        except Exception as e:
            self._run_exception_hooks(messages, e)
            raise e

        return self._run_post_hooks(messages, response)

    def structured(self, messages: MessageHistory, schema: Type[BaseModel]) -> Response:
        """Structured interaction with the model using the provided messages and output_schema."""
        messages = self._run_pre_hooks(messages)

        try:
            response = self._structured(messages, schema)
        except Exception as e:
            self._run_exception_hooks(messages, e)
            raise e

        return self._run_post_hooks(messages, response)

    async def astructured(
        self, messages: MessageHistory, schema: Type[BaseModel]
    ) -> Response:
        """Asynchronous structured interaction with the model using the provided messages and output_schema."""
        messages = self._run_pre_hooks(messages)

        try:
            response = await self._astructured(messages, schema)
        except Exception as e:
            self._run_exception_hooks(messages, e)
            raise e

        return self._run_post_hooks(messages, response)

    def chat_with_tools(self, messages: MessageHistory, tools: List[Tool]) -> Response:
        """Chat with the model using the provided messages and tools."""
        messages = self._run_pre_hooks(messages)

        try:
            response = self._chat_with_tools(messages, tools)
        except Exception as e:
            self._run_exception_hooks(messages, e)
            raise e

        return self._run_post_hooks(messages, response)

    async def achat_with_tools(
        self, messages: MessageHistory, tools: List[Tool]
    ) -> Response:
        """Asynchronous chat with the model using the provided messages and tools."""
        messages = self._run_pre_hooks(messages)

        try:
            response = await self._achat_with_tools(messages, tools)
        except Exception as e:
            self._run_exception_hooks(messages, e)
            raise e

        return self._run_post_hooks(messages, response)

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
        history = self._run_pre_hooks(messages)
        try:
            agen = self._astream_chat(history)
            async for item in agen:
                if isinstance(item, Response):
                    yield self._run_post_hooks(history, item)
                else:
                    yield item
        except Exception as e:
            self._run_exception_hooks(history, e)
            raise e

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
        history = self._run_pre_hooks(messages)
        try:
            agen = self._astream_chat_with_tools(history, tools)
            async for item in agen:
                if isinstance(item, Response):
                    yield self._run_post_hooks(history, item)
                else:
                    yield item
        except Exception as e:
            self._run_exception_hooks(history, e)
            raise e

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
        history = self._run_pre_hooks(messages)
        try:
            agen = self._astream_structured(history, schema)
            async for item in agen:
                if isinstance(item, Response):
                    yield self._run_post_hooks(history, item)
                else:
                    yield item
        except Exception as e:
            self._run_exception_hooks(history, e)
            raise e

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
