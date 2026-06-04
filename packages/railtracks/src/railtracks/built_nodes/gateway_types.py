from typing import Protocol, TypeVar

from pydantic import BaseModel

from railtracks.llm.history import MessageHistory
from railtracks.llm.response import Response
from railtracks.llm.tools.tool import Tool
from railtracks.nodes.mappers import MapInputs, MapOutputs

_TResponse = TypeVar("_TResponse")
_TResponseCo = TypeVar("_TResponseCo", covariant=True)


class GatewayCall(Protocol[_TResponseCo]):
    """The core model call as seen by gateway middleware."""

    async def __call__(
        self,
        messages: MessageHistory,
        schema: type[BaseModel] | None,
        tools: list[Tool] | None,
    ) -> _TResponseCo: ...


class GatewayWrapper(Protocol[_TResponse]):
    """Wraps a GatewayCall and returns a GatewayCall with the same signature.
    Used for retry logic, fallback models, logging, etc."""

    def __call__(
        self,
        fn: GatewayCall[_TResponse],
    ) -> GatewayCall[_TResponse]: ...


GatewayPreMapper = MapInputs[
    tuple[MessageHistory, type[BaseModel] | None, list[Tool] | None]
]
GatewayPostMapper = MapOutputs[_TResponse]
