from __future__ import annotations

import asyncio
import threading
from collections.abc import Coroutine
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


@dataclass
class _Flush:
    """Marker resolved once the consumer has written every event queued before it."""

    reached: asyncio.Future[None]


_QueueItem = Event | _EndOfStream | _Flush


@dataclass
class _Entry:
    writer: Writer
    queue: asyncio.Queue[_QueueItem]
    task: asyncio.Task[None]
    policy: QueuePolicy


class Observer:
    """Fans published events out to writers, each drained by its own consumer task.

    Writers run on a background thread with its own event loop, so runs on any loop or
    thread can share one Observer. `start()` and `shutdown()` are reference counted: the
    first `start()` brings the writers up, and the matching last `shutdown()` drains and
    stops them.
    """

    def __init__(self) -> None:
        self._writers: dict[str, _Entry] = {}
        self._drops: dict[str, int] = {}  # dropped events per writer
        self._running = False
        self._users = 0
        self._pending_writers: list[Writer] = []
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._thread_lock = threading.Lock()
        self._lifecycle_lock = asyncio.Lock()  # only used on self._loop

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
        """Take a reference on the observer, bringing the writers up on the first one.

        Safe to call from any event loop or thread. Pair every call with `shutdown()`,
        unless this call is cancelled: the reference is then released on its own.
        """
        try:
            await self._on_observer_loop(self._acquire())
        except asyncio.CancelledError:
            # The shielded acquire still completes, and the lock queues this release behind it
            asyncio.run_coroutine_threadsafe(self._release(), self._ensure_loop())
            raise

    async def shutdown(self) -> None:
        """Release a reference taken by `start()`.

        The last release drains every writer's queue and stops the writers. Earlier ones
        wait until the events published before the call have been written. Safe to call
        when the observer isn't running.
        """
        if self._users == 0:
            return
        await self._on_observer_loop(self._release())

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
        await self._on_observer_loop(
            self._register_running(writer, name, maxsize=maxsize, policy=policy)
        )

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
        flipping the flag. Runs on the observer loop."""
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
        await self._on_observer_loop(self._unregister(name))

    @property
    def is_observing(self) -> bool:
        """Whether a published event would reach at least one writer."""
        return self._running and bool(self._writers)

    @property
    def loop(self) -> asyncio.AbstractEventLoop | None:
        """The loop the writer tasks run on, or None while stopped."""
        return self._loop if self._running else None

    async def publish(self, event: Event) -> None:
        """Fan the event out to every registered writer's queue.

        Args:
            event: The event to publish.
        """
        self.publish_nowait(event)

    def publish_nowait(self, event: Event) -> None:
        """Sync body of `publish`, callable from any thread.

        The event is handed to the observer loop, so it reaches the writers after this
        returns, in the order this thread published it.

        Args:
            event: The event to publish.

        Raises:
            RuntimeError: If the observer is not running.
        """
        loop = self._loop
        if not self._running or loop is None:
            raise RuntimeError("Observer is not running.")
        loop.call_soon_threadsafe(self._fan_out, event)

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        """Return the observer loop, starting its thread on first use or after a fork."""
        with self._thread_lock:
            if (
                self._loop is None
                or self._thread is None
                or not self._thread.is_alive()
            ):
                # A dead thread (e.g. after a fork) leaves writer tasks that can never run
                self._writers.clear()
                self._drops.clear()
                self._running = False
                self._users = 0
                self._lifecycle_lock = asyncio.Lock()
                self._loop = asyncio.new_event_loop()
                self._thread = threading.Thread(
                    target=self._loop.run_forever,
                    name="railtracks-observer",
                    daemon=True,
                )
                self._thread.start()
            return self._loop

    async def _on_observer_loop(self, coro: Coroutine[object, object, None]) -> None:
        """Run `coro` on the observer loop and wait for it from the caller's loop.

        Shielded so a cancelled caller cannot interrupt a writer mid start or drain.
        """
        loop = self._ensure_loop()
        if asyncio.get_running_loop() is loop:
            await coro
            return
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        await asyncio.shield(asyncio.wrap_future(future))

    async def _acquire(self) -> None:
        async with self._lifecycle_lock:
            if self._users == 0:
                for i, writer in enumerate(self._pending_writers):
                    name = f"writer-{i}"
                    try:
                        await self._register_impl(writer, name)
                    except Exception as exc:
                        logger.warning(
                            "observability writer %r failed to start (%s: %s); "
                            "continuing without it.",
                            name,
                            type(exc).__name__,
                            exc,
                        )
                self._running = True
            self._users += 1

    async def _release(self) -> None:
        async with self._lifecycle_lock:
            if self._users == 0:
                return
            self._users -= 1
            if self._users == 0:
                self._running = False
                for name in list(self._writers.keys()):
                    await self._teardown(name)
                return
            flushed = [
                self._enqueue_flush(name, entry)
                for name, entry in self._writers.items()
            ]
        # Waited on outside the lock so other runs can start or finish meanwhile
        await asyncio.gather(*flushed)

    async def _register_running(
        self, writer: Writer, name: str, maxsize: int, policy: QueuePolicy
    ) -> None:
        async with self._lifecycle_lock:
            if not self._running:
                raise RuntimeError(
                    "Observer is not running; call start() first, or use configure_writers() "
                    "for pre-start batch registration."
                )
            await self._register_impl(writer, name, maxsize=maxsize, policy=policy)

    async def _unregister(self, name: str) -> None:
        async with self._lifecycle_lock:
            if name not in self._writers:
                raise KeyError(f"No writer registered as {name!r}.")
            await self._teardown(name)

    def _stop_thread(self) -> None:
        """Cancel writer tasks without draining and stop the thread. For test isolation."""
        with self._thread_lock:
            loop, thread = self._loop, self._thread
            self._loop = self._thread = None
            self._running = False
        if loop is None or thread is None or not thread.is_alive():
            return
        asyncio.run_coroutine_threadsafe(self._cancel_writers(), loop).result()
        loop.call_soon_threadsafe(loop.stop)
        thread.join()
        loop.close()

    async def _cancel_writers(self) -> None:
        tasks = [entry.task for entry in self._writers.values()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._writers.clear()

    def _fan_out(self, event: Event) -> None:
        """Queue the event for every writer. Runs on the observer loop."""
        if not self._running:
            logger.debug(
                "observability: dropped %s published as the observer stopped",
                event.event_type,
            )
            return
        for name, entry in self._writers.items():
            try:
                entry.queue.put_nowait(event)
            except asyncio.QueueFull:
                self._handle_full_queue(name, entry, event)

    def _handle_full_queue(
        self, name: str, entry: _Entry, item: Event | _Flush
    ) -> None:
        match entry.policy:
            case QueuePolicy.DROP_OLDEST:
                self._drop_oldest(name, entry, item)

    def _drop_oldest(self, name: str, entry: _Entry, item: Event | _Flush) -> None:
        try:
            evicted = entry.queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
        else:
            if isinstance(evicted, _Flush):
                _resolve(evicted)  # the consumer will never reach it now
        entry.queue.put_nowait(item)
        self._drops[name] += 1
        logger.warning(
            "observability writer %r queue full; dropped oldest event "
            "(policy=%s, total drops for this writer: %d)",
            name,
            entry.policy.value,
            self._drops[name],
        )

    def _enqueue_flush(self, name: str, entry: _Entry) -> asyncio.Future[None]:
        """Queue a flush marker without waiting, so a full queue never stalls the lock."""
        flush = _Flush(reached=asyncio.get_running_loop().create_future())
        try:
            entry.queue.put_nowait(flush)
        except asyncio.QueueFull:
            self._handle_full_queue(name, entry, flush)
        return flush.reached

    async def _teardown(self, name: str) -> None:
        entry = self._writers.pop(name)
        self._drops.pop(name, None)
        await entry.queue.put(_END)  # waits for room rather than evicting an event
        await entry.task
        await entry.writer.shutdown()

    async def _consumer_loop(
        self, name: str, writer: Writer, queue: asyncio.Queue[_QueueItem]
    ) -> None:
        while True:
            item = await queue.get()
            if isinstance(item, _EndOfStream):
                return
            if isinstance(item, _Flush):
                _resolve(item)
                continue
            try:
                await writer.write(item)
            except Exception as exc:
                logger.warning(
                    "observability writer %r failed on event %s: %s",
                    name,
                    item.event_id,
                    exc,
                )


def _resolve(flush: _Flush) -> None:
    if not flush.reached.done():
        flush.reached.set_result(None)
