from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum

from ..utils.logging.create import get_rt_logger
from .models import Event
from .writers.base import Writer

logger = get_rt_logger(__name__)  # for now, we can make another logger later


class QueuePolicy(Enum):
    """How a writer's queue behaves when it's full at publish time."""

    DROP_OLDEST = "drop_oldest"


class _EndOfStream:
    """Marker pushed onto a writer's queue to tell its consumer task to drain and exit."""


_END = _EndOfStream()

_QueueItem = Event | _EndOfStream


@dataclass
class _Entry:
    writer: Writer
    queue: asyncio.Queue[_QueueItem]
    task: asyncio.Task[None]
    policy: QueuePolicy


class Observer:
    def __init__(self) -> None:
        self._writers: dict[str, _Entry] = {}
        self._drops: dict[str, int] = {}  # dropped events per writer
        self._running = False
        self._pending_writers: list[Writer] = []
        self._start_lock: asyncio.Lock = asyncio.Lock()

    # async context manager support added for now, this will become more clear
    # once we move to integrating with the other modules
    async def __aenter__(self) -> Observer:
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.shutdown()

    def configure_writers(self, writers: list[Writer]) -> None:
        """Register writers in bulk, to be brought up on the next `start()`.

        Must be called before `start()` — raises `RuntimeError` if the observer
        is already running. Replaces any previously configured pending writers.
        """
        if self._running:
            raise RuntimeError(
                "configure_writers must be called before start(); use register() to add writers after."
            )
        self._pending_writers = list(writers)

    async def start(self) -> None:
        """Bring up the observer.

        This is idempotent safe to call multiple times.
        """
        if self._running:
            return
        async with self._start_lock:
            if self._running:
                return
            for i, writer in enumerate(self._pending_writers):
                await self._register_impl(writer, f"writer-{i}")
            self._running = True

    async def shutdown(self) -> None:
        if not self._running:
            return
        self._running = False
        for name in list(self._writers.keys()):
            await self._teardown(name)

    async def register(
        self,
        writer: Writer,
        name: str,
        maxsize: int = 10_000,
        policy: QueuePolicy = QueuePolicy.DROP_OLDEST,
    ) -> None:
        """Register a writer on a running observer. Post-start only.

        For a pre-start batch, use `configure_writers()` and let `start()`
        register them.
        """
        if not self._running:
            raise RuntimeError(
                "Observer is not running; call start() first, or use configure_writers() "
                "for pre-start batch registration."
            )
        await self._register_impl(writer, name, maxsize=maxsize, policy=policy)

    async def _register_impl(
        self,
        writer: Writer,
        name: str,
        maxsize: int = 10_000,
        policy: QueuePolicy = QueuePolicy.DROP_OLDEST,
    ) -> None:
        """Internal registration path used by both public `register` (post-start)
        and `start()` (registering pending writers during startup). Skips the
        `_running` check so `start()` can register pending writers before
        flipping the flag."""
        if name in self._writers:
            raise ValueError(f"Writer {name!r} is already registered.")
        await writer.start()
        queue: asyncio.Queue[_QueueItem] = asyncio.Queue(
            maxsize=maxsize
        )  # Each writer has its own queue
        task = asyncio.create_task(
            self._consumer_loop(name, writer, queue),
            name=f"observer-consumer:{name}",
        )
        self._writers[name] = _Entry(
            writer=writer, queue=queue, task=task, policy=policy
        )
        self._drops[name] = 0

    async def unregister(self, name: str) -> None:
        if name not in self._writers:
            raise KeyError(f"No writer registered as {name!r}.")
        await self._teardown(name)

    def publish(self, event: Event) -> None:
        """Fan the event out to every registered writer's queue.

        Args:
            event: The event to publish.
        """
        if not self._running:
            raise RuntimeError("Observer is not running.")
        for name, entry in self._writers.items():
            try:
                entry.queue.put_nowait(event)
            except asyncio.QueueFull:
                self._handle_full_queue(name, entry, event)

    def _handle_full_queue(self, name: str, entry: _Entry, event: Event) -> None:
        match entry.policy:
            case QueuePolicy.DROP_OLDEST:
                self._drop_oldest(name, entry, event)

    def _drop_oldest(self, name: str, entry: _Entry, event: Event) -> None:
        try:
            entry.queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
        entry.queue.put_nowait(event)
        self._drops[name] += 1
        logger.warning(
            "observability writer %r queue full; dropped oldest event "
            "(policy=%s, total drops for this writer: %d)",
            name,
            entry.policy.value,
            self._drops[name],
        )

    async def _teardown(self, name: str) -> None:
        entry = self._writers.pop(name)
        self._drops.pop(name, None)
        _enqueue_end(entry.queue)
        await entry.task
        await entry.writer.shutdown()

    async def _consumer_loop(
        self, name: str, writer: Writer, queue: asyncio.Queue[_QueueItem]
    ) -> None:
        while True:
            item = await queue.get()
            if isinstance(item, _EndOfStream):
                return
            try:
                await writer.write(item)
            except Exception as exc:
                logger.warning(
                    "observability writer %r failed on event %s: %s",
                    name,
                    item.event_id,
                    exc,
                )


def _enqueue_end(queue: asyncio.Queue[_QueueItem]) -> None:
    try:
        queue.put_nowait(_END)
    except asyncio.QueueFull:
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
        queue.put_nowait(_END)
