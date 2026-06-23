from abc import ABC
from typing import Awaitable, Callable, TypeVar

from pydantic import BaseModel

from railtracks.utils.profiling import Stamp


class RTEvent(BaseModel, ABC):
    node_id: str | None = None
    run_id: str | None = None
    timestamp: float = 0.0
    stamp: Stamp | None = None

    model_config = {"arbitrary_types_allowed": True}


_TEvent = TypeVar("_TEvent", bound=RTEvent)


class Observer:
    def __init__(
            self,
            name: str,
            stamp_creator: Callable[[str], Stamp] | None = None,
    ):
        self._observations: dict[type[RTEvent], list[Callable[..., Awaitable[None]]]] = {}
        self._log: list[RTEvent] = []
        self._stamp_creator = stamp_creator
        self.name = name

    def observe(
            self,
            event_type: type[_TEvent],
            callback: Callable[[_TEvent], Awaitable[None]],
    ) -> None:
        self._observations.setdefault(event_type, []).append(callback)

    async def post_event(
            self,
            event: RTEvent,
    ) -> None:
        if self._stamp_creator is not None:
            event.stamp = self._stamp_creator(type(event).__name__)
        self._log.append(event)
        for callback in self._observations.get(type(event), []):
            await callback(event)

    def events_for(self, node_id: str) -> list[RTEvent]:
        return [e for e in self._log if e.node_id == node_id]

    @property
    def events(self) -> list[RTEvent]:
        return list(self._log)
