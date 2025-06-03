###
# In the following document, we will use the interface types defined in this module to interact with the llama index to
# route to a given model.
###
from typing import List


from pydantic import BaseModel


from .history import MessageHistory
from .response import Response
from .tools import Tool

from abc import ABC, abstractmethod


class ModelBase(ABC):
    @abstractmethod
    def chat(self, messages: MessageHistory, **kwargs) -> Response:
        pass

    @abstractmethod
    def structured(
        self, messages: MessageHistory, schema: BaseModel, **kwargs
    ) -> Response:
        pass

    @abstractmethod
    def stream_chat(self, messages: MessageHistory, **kwargs) -> Response:
        pass

    @abstractmethod
    def chat_with_tools(
        self, messages: MessageHistory, tools: List[Tool], **kwargs
    ) -> Response:
        pass
