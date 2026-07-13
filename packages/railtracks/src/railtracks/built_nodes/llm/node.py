from __future__ import annotations


from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from railtracks.built_nodes._node_builder import UserInput
from railtracks.built_nodes.concrete.response import StringResponse, StructuredResponse
from railtracks.built_nodes.middlewares.core import ModelMiddleware
from railtracks.llm.history import MessageHistory
from railtracks.llm.response import Response
from railtracks.llm.tools.tool import Tool
from railtracks.middlewares.chain import MiddlewareChain
from railtracks.nodes.nodes import Node

from pydantic import BaseModel

_R = TypeVar("_R", bound=StringResponse | StructuredResponse)


class LLMNode(ABC, Node[[UserInput], _R], Generic[_R]):
    model_middleware: MiddlewareChain[[MessageHistory, type[BaseModel] | None, list[Tool] | None], Response]

    @abstractmethod
    def extend_model_middleware(self, *model_middleware: ModelMiddleware) -> type[LLMNode[_R]]: 
        model_middleware = MiddlewareChain(self.model_middleware.middleware + list(model_middleware))

