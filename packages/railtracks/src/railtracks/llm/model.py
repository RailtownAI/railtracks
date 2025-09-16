###
# In the following document, we will use the interface types defined in this module to interact with the llama index to
# route to a given model.
###
from abc import ABC, abstractmethod
from typing import Callable, List, Type

from pydantic import BaseModel

from .history import MessageHistory
from .response import Response
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
        pre_hooks: List[Callable[[MessageHistory], MessageHistory]] | None = None,
        post_hooks: List[Callable[[MessageHistory, Response], Response]] | None = None,
        exception_hooks: List[Callable[[MessageHistory, Exception], None]]
        | None = None,
    ):
        if pre_hooks is None:
            pre_hooks: List[Callable[[MessageHistory], MessageHistory]] = []

        if post_hooks is None:
            post_hooks: List[Callable[[MessageHistory, Response], Response]] = []

        if exception_hooks is None:
            exception_hooks: List[Callable[[MessageHistory, Exception], None]] = []

        self._pre_hooks = pre_hooks
        self._post_hooks = post_hooks
        self._exception_hooks = exception_hooks

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

    @classmethod
    @abstractmethod
    def model_type(cls) -> str:
        """The name of the provider of this model or the model type."""
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

    def chat(self, messages: MessageHistory, **kwargs):
        """Chat with the model using the provided messages."""

        messages = self._run_pre_hooks(messages)

        try:
            response = self._chat(messages, **kwargs)
        except Exception as e:
            self._run_exception_hooks(messages, e)
            raise e

        response = self._run_post_hooks(messages, response)
        return response

    async def achat(self, messages: MessageHistory, **kwargs):
        """Asynchronous chat with the model using the provided messages."""
        messages = self._run_pre_hooks(messages)

        try:
            response = await self._achat(messages, **kwargs)
        except Exception as e:
            self._run_exception_hooks(messages, e)
            raise e

        response = self._run_post_hooks(messages, response)

        return response

    def structured(self, messages: MessageHistory, schema: Type[BaseModel], **kwargs):
        """Structured interaction with the model using the provided messages and output_schema."""
        messages = self._run_pre_hooks(messages)

        try:
            response = self._structured(messages, schema, **kwargs)
        except Exception as e:
            self._run_exception_hooks(messages, e)
            raise e

        response = self._run_post_hooks(messages, response)

        return response

    async def astructured(
        self, messages: MessageHistory, schema: Type[BaseModel], **kwargs
    ):
        """Asynchronous structured interaction with the model using the provided messages and output_schema."""
        messages = self._run_pre_hooks(messages)

        try:
            response = await self._astructured(messages, schema, **kwargs)
        except Exception as e:
            self._run_exception_hooks(messages, e)
            raise e

        response = self._run_post_hooks(messages, response)

        return response

    def stream_chat(self, messages: MessageHistory, **kwargs):
        """Stream chat with the model using the provided messages."""
        messages = self._run_pre_hooks(messages)

        try:
            response = self._stream_chat(messages, **kwargs)
        except Exception as e:
            self._run_exception_hooks(messages, e)
            raise e

        response = self._run_post_hooks(messages, response)

        return response

    async def astream_chat(self, messages: MessageHistory, **kwargs):
        """Asynchronous stream chat with the model using the provided messages."""
        messages = self._run_pre_hooks(messages)

        try:
            response = await self._astream_chat(messages, **kwargs)
        except Exception as e:
            self._run_exception_hooks(messages, e)
            raise e

        response = self._run_post_hooks(messages, response)

        return response

    def chat_with_tools(self, messages: MessageHistory, tools: List[Tool], **kwargs):
        """Chat with the model using the provided messages and tools."""
        messages = self._run_pre_hooks(messages)

        try:
            response = self._chat_with_tools(messages, tools, **kwargs)
        except Exception as e:
            self._run_exception_hooks(messages, e)
            raise e

        response = self._run_post_hooks(messages, response)
        return response

    async def achat_with_tools(
        self, messages: MessageHistory, tools: List[Tool], **kwargs
    ):
        """Asynchronous chat with the model using the provided messages and tools."""
        messages = self._run_pre_hooks(messages)

        try:
            response = await self._achat_with_tools(messages, tools, **kwargs)
        except Exception as e:
            self._run_exception_hooks(messages, e)
            raise e

        response = self._run_post_hooks(messages, response)

        return response

    @abstractmethod
    def _chat(self, messages: MessageHistory, **kwargs) -> Response:
        pass

    @abstractmethod
    def _structured(
        self, messages: MessageHistory, schema: Type[BaseModel], **kwargs
    ) -> Response:
        pass

    @abstractmethod
    def _stream_chat(self, messages: MessageHistory, **kwargs) -> Response:
        pass

    @abstractmethod
    def _chat_with_tools(
        self, messages: MessageHistory, tools: List[Tool], **kwargs
    ) -> Response:
        pass

    @abstractmethod
    async def _achat(self, messages: MessageHistory, **kwargs) -> Response:
        pass

    @abstractmethod
    async def _astructured(
        self, messages: MessageHistory, schema: Type[BaseModel], **kwargs
    ) -> Response:
        pass

    @abstractmethod
    async def _astream_chat(self, messages: MessageHistory, **kwargs) -> Response:
        pass

    @abstractmethod
    async def _achat_with_tools(
        self, messages: MessageHistory, tools: List[Tool], **kwargs
    ) -> Response:
        pass
