###
# In the following document, we will use the interface types defined in this module to interact with the llama index to
# route to a given model.
###
from typing import List, Callable

from pydantic import BaseModel


from .history import MessageHistory
from .response import Response
from .tools import Tool

from abc import ABC, abstractmethod


class ModelBase(ABC):
    """
    A simple base that represents the behavior of a model that can be used for chat, structured interactions, and streaming.

    The base class allows for the insertion of hooks that can modify the messages before they are sent to the model,
    response after they are received, and map exceptions that may occur during the interaction.

    All the hooks are optional and can be added or removed as needed.
    """

    def __init__(
        self,
        pre_hook: List[Callable[[MessageHistory], MessageHistory]] | None = None,
        post_hook: List[Callable[[MessageHistory, Response], Response]] | None = None,
        exception_hook: List[Callable[[MessageHistory, Exception], None]] | None = None,
    ):
        if pre_hook is None:
            pre_hook: List[Callable[[MessageHistory], MessageHistory]] = []

        if post_hook is None:
            post_hook: List[Callable[[MessageHistory, Response], Response]] = []

        if exception_hook is None:
            exception_hook: List[Callable[[MessageHistory, Exception], None]] = []

        self._pre_hook = pre_hook
        self._post_hook = post_hook
        self._exception_hook = exception_hook

    def add_pre_hook(self, hook: Callable[[MessageHistory], MessageHistory]) -> None:
        """Adds a pre-hook to modify messages before sending them to the model."""
        self._pre_hook.append(hook)

    def add_post_hook(
        self, hook: Callable[[MessageHistory, Response], Response]
    ) -> None:
        """Adds a post-hook to modify the response after receiving it from the model."""
        self._post_hook.append(hook)

    def add_exception_hook(
        self, hook: Callable[[MessageHistory, Exception], None]
    ) -> None:
        """Adds an exception hook to handle exceptions during model interactions."""
        self._exception_hook.append(hook)

    def remove_pre_hooks(self) -> None:
        """Removes all of the hooks that modify messages before sending them to the model."""
        self._pre_hook = []

    def remove_post_hooks(self) -> None:
        """Removes all of the hooks that modify the response after receiving it from the model."""
        self._post_hook = []

    def remove_exception_hooks(self) -> None:
        """Removes all of the hooks that handle exceptions during model interactions."""
        self._exception_hook = []

    @abstractmethod
    def model_name(self) -> str | None:
        """
        Returns the name of the model being used.

        It can be treated as unique identifier for the model when paired with the `model_type`.
        """
        return None

    @classmethod
    @abstractmethod
    def model_type(cls) -> str | None:
        """The name of the provider of this model or the model type."""
        return None

    def _run_pre_hooks(self, message_history: MessageHistory) -> MessageHistory:
        """Runs all pre-hooks on the provided message history."""
        for hook in self._pre_hook:
            message_history = hook(message_history)
        return message_history

    def _run_post_hooks(
        self, message_history: MessageHistory, result: Response
    ) -> Response:
        """Runs all post-hooks on the provided message history and result."""
        for hook in self._post_hook:
            result = hook(message_history, result)
        return result

    def _run_exception_hooks(
        self, message_history: MessageHistory, exception: Exception
    ) -> None:
        """Runs all exception hooks on the provided message history and exception."""
        for hook in self._exception_hook:
            hook(message_history, exception)

    def chat(self, messages: MessageHistory, **kwargs):
        """Chat with the model using the provided messages."""

        messages = self._run_pre_hooks(messages)

        try:
            response = self._chat(messages, **kwargs)
        except:
            self._run_exception_hooks(messages, Exception("Error during chat"))
            raise

        response = self._run_post_hooks(messages, response)
        return response

    async def achat(self, messages: MessageHistory, **kwargs):
        """Asynchronous chat with the model using the provided messages."""
        messages = self._run_pre_hooks(messages)

        try:
            response = await self._achat(messages, **kwargs)
        except:
            self._run_exception_hooks(messages, Exception("Error during async chat"))
            raise

        response = self._run_post_hooks(messages, response)

        return response

    def structured(self, messages: MessageHistory, schema: BaseModel, **kwargs):
        """Structured interaction with the model using the provided messages and schema."""
        messages = self._run_pre_hooks(messages)

        try:
            response = self._structured(messages, schema, **kwargs)
        except:
            self._run_exception_hooks(
                messages, Exception("Error during structured interaction")
            )
            raise

        response = self._run_post_hooks(messages, response)

        return response

    async def astructured(self, messages: MessageHistory, schema: BaseModel, **kwargs):
        """Asynchronous structured interaction with the model using the provided messages and schema."""
        messages = self._run_pre_hooks(messages)

        try:
            response = await self._astructured(messages, schema, **kwargs)
        except:
            self._run_exception_hooks(
                messages, Exception("Error during async structured interaction")
            )
            raise

        response = self._run_post_hooks(messages, response)

        return response

    def stream_chat(self, messages: MessageHistory, **kwargs):
        """Stream chat with the model using the provided messages."""
        messages = self._run_pre_hooks(messages)

        try:
            response = self._stream_chat(messages, **kwargs)
        except:
            self._run_exception_hooks(messages, Exception("Error during stream chat"))
            raise

        response = self._run_post_hooks(messages, response)

        return response

    async def astream_chat(self, messages: MessageHistory, **kwargs):
        """Asynchronous stream chat with the model using the provided messages."""
        messages = self._run_pre_hooks(messages)

        try:
            response = await self._astream_chat(messages, **kwargs)
        except:
            self._run_exception_hooks(
                messages, Exception("Error during async stream chat")
            )
            raise

        response = self._run_post_hooks(messages, response)

        return response

    def chat_with_tools(self, messages: MessageHistory, tools: List[Tool], **kwargs):
        """Chat with the model using the provided messages and tools."""
        messages = self._run_pre_hooks(messages)

        try:
            response = self._chat_with_tools(messages, tools, **kwargs)
        except:
            self._run_exception_hooks(
                messages, Exception("Error during chat with tools")
            )
            raise

        response = self._run_post_hooks(messages, response)
        return response

    async def achat_with_tools(
        self, messages: MessageHistory, tools: List[Tool], **kwargs
    ):
        """Asynchronous chat with the model using the provided messages and tools."""
        messages = self._run_pre_hooks(messages)

        try:
            response = await self._achat_with_tools(messages, tools, **kwargs)
        except:
            self._run_exception_hooks(
                messages, Exception("Error during async chat with tools")
            )
            raise

        response = self._run_post_hooks(messages, response)

        return response

    @abstractmethod
    def _chat(self, messages: MessageHistory, **kwargs) -> Response:
        pass

    @abstractmethod
    def _structured(
        self, messages: MessageHistory, schema: BaseModel, **kwargs
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
        self, messages: MessageHistory, schema: BaseModel, **kwargs
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
