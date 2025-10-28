###
# In the following document, we will use the interface types defined in this module to interact with the llama index to
# route to a given model.
###
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import (
    AsyncGenerator,
    Callable,
    Generator,
    Generic,
    List,
    Literal,
    Type,
    TypeVar,
    overload,
)

from pydantic import BaseModel

from .history import MessageHistory
from .providers import ModelProvider
from .response import Response
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
        self.stream = stream

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

        response = self._run_post_hooks(messages, response)

        return response

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
