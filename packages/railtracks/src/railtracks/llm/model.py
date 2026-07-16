###
# In the following document, we will use the interface types defined in this module to interact with the llama index to
# route to a given model.
###
from __future__ import annotations

import warnings
from abc import ABC, abstractmethod
from typing import (
    AsyncGenerator,
    Callable,
    Generator,
    Generic,
    List,
    Literal,
    Sequence,
    Type,
    TypeVar,
    overload,
)

from pydantic import BaseModel

from .history import MessageHistory
from .message import Message
from .providers import ModelProvider
from .response import Response
from .retries.base import RetryApproach
from .tools import Tool

_TStream = TypeVar("_TStream", Literal[True], Literal[False])


class ModelBase(ABC, Generic[_TStream]):
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
        stream: _TStream = False,
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

        if stream:
            warnings.warn(
                "Constructing a model with stream=True is deprecated. Streaming is now "
                "requested at the call site: use `rt.astream(...)` (or a `stream_callback` "
                "on your Session/Flow) instead, or call `model.astream_chat(...)` directly "
                "for a one-off streamed model request.",
                DeprecationWarning,
                stacklevel=3,
            )

        self._pre_hooks = pre_hooks
        self._post_hooks = post_hooks
        self._exception_hooks = exception_hooks
        self.stream = stream
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

    def generator_wrapper(
        self,
        generator: Generator[str | Response, None, Response],
        message_history: MessageHistory,
    ) -> Generator[str | Response, None, Response]:
        new_response: Response | None = None
        for g in generator:
            if isinstance(g, Response):
                g.message_info
                new_response = self._run_post_hooks(message_history, g)
                yield new_response

            yield g

        assert new_response is not None, (
            "The generator did not yield a final Response object so nothing could be done."
        )

        return new_response

    @overload
    def chat(self: ModelBase[Literal[False]], messages: MessageHistory) -> Response:
        pass

    @overload
    def chat(
        self: ModelBase[Literal[True]], messages: MessageHistory
    ) -> Generator[str | Response, None, Response]:
        pass

    def chat(
        self, messages: MessageHistory
    ) -> Response | Generator[str | Response, None, Response]:
        """Chat with the model using the provided messages."""

        messages = self._run_pre_hooks(messages)

        try:
            response = self._chat(messages)
        except Exception as e:
            self._run_exception_hooks(messages, e)
            raise e

        if isinstance(response, Generator):
            return self.generator_wrapper(response, messages)

        response = self._run_post_hooks(messages, response)
        return response

    @overload
    async def achat(
        self: ModelBase[Literal[False]], messages: MessageHistory
    ) -> Response:
        pass

    @overload
    async def achat(
        self: ModelBase[Literal[True]], messages: MessageHistory
    ) -> Generator[str | Response, None, Response]:
        pass

    async def achat(self, messages: MessageHistory):
        """Asynchronous chat with the model using the provided messages."""
        messages = self._run_pre_hooks(messages)

        try:
            response = await self._achat(messages)
        except Exception as e:
            self._run_exception_hooks(messages, e)
            raise e

        if isinstance(response, Generator):
            return self.generator_wrapper(response, messages)
        if isinstance(response, AsyncGenerator):
            # deprecated constructor-level stream=True path: pass the stream through untouched
            return response

        response = self._run_post_hooks(messages, response)

        return response

    @overload
    def structured(
        self: ModelBase[Literal[False]],
        messages: MessageHistory,
        schema: Type[BaseModel],
    ) -> Response:
        pass

    @overload
    def structured(
        self: ModelBase[Literal[True]],
        messages: MessageHistory,
        schema: Type[BaseModel],
    ) -> Generator[str | Response, None, Response]:
        pass

    def structured(self, messages: MessageHistory, schema: Type[BaseModel]):
        """Structured interaction with the model using the provided messages and output_schema."""
        messages = self._run_pre_hooks(messages)

        try:
            response = self._structured(messages, schema)
        except Exception as e:
            self._run_exception_hooks(messages, e)
            raise e

        if isinstance(response, Generator):
            return self.generator_wrapper(response, messages)

        response = self._run_post_hooks(messages, response)

        return response

    @overload
    async def astructured(
        self: ModelBase[Literal[False]],
        messages: MessageHistory,
        schema: Type[BaseModel],
    ) -> Response:
        pass

    @overload
    async def astructured(
        self: ModelBase[Literal[True]],
        messages: MessageHistory,
        schema: Type[BaseModel],
    ) -> Generator[str | Response, None, Response]:
        pass

    async def astructured(self, messages: MessageHistory, schema: Type[BaseModel]):
        """Asynchronous structured interaction with the model using the provided messages and output_schema."""
        messages = self._run_pre_hooks(messages)

        try:
            response = await self._astructured(messages, schema)
        except Exception as e:
            self._run_exception_hooks(messages, e)
            raise e

        if isinstance(response, Generator):
            return self.generator_wrapper(response, messages)
        if isinstance(response, AsyncGenerator):
            # deprecated constructor-level stream=True path: pass the stream through untouched
            return response

        response = self._run_post_hooks(messages, response)

        return response

    @overload
    def chat_with_tools(
        self: ModelBase[Literal[False]], messages: MessageHistory, tools: List[Tool]
    ) -> Response:
        pass

    @overload
    def chat_with_tools(
        self: ModelBase[Literal[True]], messages: MessageHistory, tools: List[Tool]
    ) -> Generator[str | Response, None, Response]:
        pass

    def chat_with_tools(self, messages: MessageHistory, tools: List[Tool]):
        """Chat with the model using the provided messages and tools."""
        messages = self._run_pre_hooks(messages)

        try:
            response = self._chat_with_tools(messages, tools)
        except Exception as e:
            self._run_exception_hooks(messages, e)
            raise e

        if isinstance(response, Generator):
            return self.generator_wrapper(response, messages)

        response = self._run_post_hooks(messages, response)
        return response

    @overload
    async def achat_with_tools(
        self: ModelBase[Literal[False]], messages: MessageHistory, tools: List[Tool]
    ) -> Response:
        pass

    @overload
    async def achat_with_tools(
        self: ModelBase[Literal[True]], messages: MessageHistory, tools: List[Tool]
    ) -> Generator[str | Response, None, Response]:
        pass

    async def achat_with_tools(self, messages: MessageHistory, tools: List[Tool]):
        """Asynchronous chat with the model using the provided messages and tools."""
        messages = self._run_pre_hooks(messages)

        try:
            response = await self._achat_with_tools(messages, tools)
        except Exception as e:
            self._run_exception_hooks(messages, e)
            raise e

        if isinstance(response, Generator):
            return self.generator_wrapper(response, messages)
        if isinstance(response, AsyncGenerator):
            # deprecated constructor-level stream=True path: pass the stream through untouched
            return response

        response = self._run_post_hooks(messages, response)

        return response

    # ================ START Streaming (per-call) LLM calls ===============
    # These methods request a streamed response for a single call, regardless of how the model
    # was constructed. They are the model-level building blocks of railtracks streaming (see
    # `rt.astream` and `rt.broadcast_stream`).

    @staticmethod
    def _coerce_message_history(
        messages: MessageHistory | Sequence[Message],
    ) -> MessageHistory:
        """Normalizes a plain sequence of messages into a MessageHistory."""
        if isinstance(messages, MessageHistory):
            return messages
        return MessageHistory(list(messages))

    async def astream_chat(
        self, messages: MessageHistory | Sequence[Message]
    ) -> AsyncGenerator[str | Response, None]:
        """
        Chat with the model, streaming the response.

        Returns an async generator that yields `str` token chunks as they arrive, followed by a
        single final `Response` object containing the complete message (and usage info).

        ```python
        async for item in model.astream_chat([UserMessage("hi")]):
            if isinstance(item, str):
                ...  # token chunk
            else:
                final = item  # the terminal Response
        ```

        Tip: inside a node, prefer `await rt.broadcast_stream(model.astream_chat(...))`, which
        forwards the chunks to whoever is consuming the run and returns the final `Response`.

        Args:
            messages: The conversation so far — a `MessageHistory` or any sequence of
                `Message` objects (e.g. a plain list of `UserMessage`s).

        Yields:
            str | Response: `str` token chunks, then one final complete `Response`.
        """
        history = self._coerce_message_history(messages)
        history = self._run_pre_hooks(history)
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
        self, messages: MessageHistory | Sequence[Message], tools: List[Tool]
    ) -> AsyncGenerator[str | Response, None]:
        """
        Chat with the model using tools, streaming the response.

        Yields `str` content chunks as they arrive, followed by a single final `Response`. The
        final `Response` contains either the complete assistant text or the requested tool
        calls (tool-call deltas are accumulated internally and are not yielded as chunks).

        Args:
            messages: The conversation so far — a `MessageHistory` or any sequence of
                `Message` objects.
            tools: The tools to make available to the model.

        Yields:
            str | Response: `str` content chunks, then one final complete `Response`.
        """
        history = self._coerce_message_history(messages)
        history = self._run_pre_hooks(history)
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
        self, messages: MessageHistory | Sequence[Message], schema: Type[BaseModel]
    ) -> AsyncGenerator[str | Response, None]:
        """
        Structured interaction with the model, streaming the response.

        Yields the raw (JSON) `str` chunks as they arrive, followed by a single final
        `Response` whose message content is the parsed `schema` instance.

        Note the chunks are unvalidated JSON fragments; validation only happens once the stream
        completes, so a schema mismatch surfaces at the end of the stream.

        Args:
            messages: The conversation so far — a `MessageHistory` or any sequence of
                `Message` objects.
            schema: The pydantic model the response must conform to.

        Yields:
            str | Response: raw JSON `str` chunks, then one final complete `Response`.
        """
        history = self._coerce_message_history(messages)
        history = self._run_pre_hooks(history)
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
    def _chat(
        self, messages: MessageHistory
    ) -> Response | Generator[str | Response, None, Response]:
        pass

    @abstractmethod
    def _structured(
        self, messages: MessageHistory, schema: Type[BaseModel]
    ) -> Response | Generator[str | Response, None, Response]:
        pass

    @abstractmethod
    def _chat_with_tools(
        self, messages: MessageHistory, tools: List[Tool]
    ) -> Response | Generator[str | Response, None, Response]:
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
    async def _achat(
        self, messages: MessageHistory
    ) -> Response | AsyncGenerator[str | Response, None]:
        pass

    @abstractmethod
    async def _astructured(
        self,
        messages: MessageHistory,
        schema: Type[BaseModel],
    ) -> Response | AsyncGenerator[str | Response, None]:
        pass

    @abstractmethod
    async def _achat_with_tools(
        self, messages: MessageHistory, tools: List[Tool]
    ) -> Response | AsyncGenerator[str | Response, None]:
        pass
