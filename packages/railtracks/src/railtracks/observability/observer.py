from __future__ import annotations

import inspect
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field

from .models import Event
from .writers.base import Writer

# a plain logger under RT, so observability doesn't depend on railtracks' logging
logger = logging.getLogger(f"RT.{__name__}")


@dataclass
class _Sink:
    """A writer or inline listener, and the lock that serializes calls to it."""

    name: str
    deliver: Callable[[Event], None]
    writer: Writer | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)

    def __call__(self, event: Event) -> None:
        with self.lock:
            try:
                self.deliver(event)
            except Exception as exc:
                logger.warning(
                    "observability: %s failed on %s: %r",
                    self.name,
                    event.event_type,
                    exc,
                )


class Observer:
    """Delivers each published event to inline listeners and writers on the publishing thread.

    Writers start on the first event and are shut down once, by `shutdown()`. Each listener
    and writer is called under its own lock, so neither has to be thread-safe.

    Args:
        default_writers: Builds the writers to start on the first event when none were
            configured.
    """

    def __init__(
        self, default_writers: Callable[[], list[Writer]] | None = None
    ) -> None:
        self._default_writers = default_writers
        self._lock = threading.Lock()
        self._pending: list[Writer] = []
        self._writers: tuple[_Sink, ...] = ()
        self._listeners: tuple[_Sink, ...] = ()
        self._started = False
        self._closed = False

    def configure_writers(self, writers: list[Writer]) -> None:
        """Replace the writers. Safe to call at any time.

        Before the first event, the writers start with it. After that, they start now
        and the writers they replace are shut down.

        Args:
            writers: The writers to deliver events to.

        Raises:
            TypeError: If a writer's `start`, `write` or `shutdown` is async.
        """
        for writer in writers:
            _check_sync(writer)
        with self._lock:
            if not self._started:
                self._pending = list(writers)
                return
            replaced = self._writers
            self._writers = _start_writers(writers)
        for sink in replaced:
            _shutdown_writer(sink)

    def add_listener(self, listener: Callable[[Event], None]) -> bool:
        """Register a listener called with every event, unless it is already registered.

        Args:
            listener: Called on the publishing thread, before the writers.

        Returns:
            Whether the listener was added.
        """
        with self._lock:
            if any(sink.deliver == listener for sink in self._listeners):
                return False
            name = getattr(listener, "__qualname__", repr(listener))
            self._listeners = (*self._listeners, _Sink(name=name, deliver=listener))
            return True

    @property
    def listeners(self) -> list[Callable[[Event], None]]:
        return [sink.deliver for sink in self._listeners]

    @property
    def is_observing(self) -> bool:
        """Whether a published event would reach at least one writer."""
        self._ensure_started()
        return not self._closed and bool(self._writers)

    def publish(self, event: Event) -> None:
        """Deliver the event to every listener, then every writer, before returning.

        Callable from any thread.

        Args:
            event: The event to publish.
        """
        self._ensure_started()
        if self._closed:
            return
        for sink in self._listeners:
            sink(event)
        for sink in self._writers:
            sink(event)

    def shutdown(self) -> None:
        """Shut down every writer. Safe to call more than once.

        Later events are ignored, and the Observer can't be started again.
        """
        with self._lock:
            if self._closed:
                return
            self._closed = True
            writers = self._writers
        for sink in writers:
            _shutdown_writer(sink)

    def _ensure_started(self) -> None:
        if self._started:
            return
        with self._lock:
            if self._started:
                return
            writers = self._pending
            if not writers and self._default_writers is not None:
                writers = self._default_writers()
            self._writers = _start_writers(writers)
            self._started = True


def _check_sync(writer: Writer) -> None:
    for method in ("start", "write", "shutdown"):
        if inspect.iscoroutinefunction(getattr(writer, method, None)):
            raise TypeError(
                f"{type(writer).__name__}.{method} is async; "
                "observability writers must be synchronous"
            )


def _start_writers(writers: list[Writer]) -> tuple[_Sink, ...]:
    sinks: list[_Sink] = []
    for i, writer in enumerate(writers):
        name = f"writer-{i}"
        try:
            writer.start()
        except Exception as exc:
            logger.warning(
                "observability writer %r failed to start (%r); continuing without it.",
                name,
                exc,
            )
            continue
        sinks.append(_Sink(name=name, deliver=writer.write, writer=writer))
    return tuple(sinks)


def _shutdown_writer(sink: _Sink) -> None:
    with sink.lock:
        if sink.writer is not None:
            try:
                sink.writer.shutdown()
            except Exception as exc:
                logger.warning(
                    "observability writer %r failed to shut down: %r", sink.name, exc
                )
