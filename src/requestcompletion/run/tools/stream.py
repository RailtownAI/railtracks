from __future__ import annotations

import queue
import time

import warnings
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import TypeVar, Generic, List, Optional, Dict


T = TypeVar("T")


class Subscriber(ABC, Generic[T]):
    """A simple interface that defines the requirements for a subscriber to a data stream."""

    @abstractmethod
    def handle(self, item: T) -> None: ...

    @classmethod
    def null_concrete_sub(cls):
        """A simple factory method that creates a null concrete subscriber that does nothing. It can be attached and
        will do nothing."""

        return NullConcreteSub


class DataStream(Generic[T]):
    """The DataStream class is simple class that allows for the publication of data that is handled by the defined
    set of subscribers. The class is designed to adhere to the following conditions:

    1. Each subscriber will handle the data in the order it was published. (It will wait until it has handled one piece
    of data before moving on to the next)
    2. The stream will not close until all the data has been handled by the subscribers unless you force it to.
    3. Each listener will operate on a separate thread of execution
    """

    def __init__(
        self,
        subscribers: Optional[List[Subscriber[T]]] = None,
    ):
        """
        Creates a new instance of a Data stream with the given subscribers.

        Notes: The stream will start running and will only stop operating once you call `stop()`
        - The number of running threads is equal to the number of subscribers.
        Args:
            subscribers: A list of subscribers you would like to attach (defaults to 0)
        """
        self._subscribers = subscribers if subscribers is not None else []

        # Each sub will have its own queue to maintain ordering of the handling.
        self._queues: Dict[Subscriber, queue.Queue] = {subscriber: queue.Queue() for subscriber in self._subscribers}
        # default to running.
        self._running = True

        self._executor = ThreadPoolExecutor(max_workers=len(self._subscribers) + 1)
        self._futures = []

        # create a separate execution thread for each sub.
        for subscriber in self._subscribers:
            self._futures.append(self._executor.submit(self._listener, subscriber))

    @property
    def is_unhandled(self):
        """Is there any outstanding data publish which is waiting to be collected by the subscribers."""
        # thankfully queues are thread safe so we dont have to worry about concurrent reads and writes
        return any([not q.empty() for q in self._queues.values()])

    def publish(self, item: T):
        """
        Publishes an item to the stream.

        Note this action will automatically trigger the listeners to pick up the data and handle it.
        """
        for subscriber in self._subscribers:
            self._queues[subscriber].put(item)

    def _listener(self, subscriber: Subscriber[T]):
        """
        A function that should be run for each subscriber to handle any data updates.

        This is the function which handles the ordering and execution of the listener responses
        """
        while self._running:
            try:
                item = self._queues[subscriber].get(timeout=0.1)
                print("collected item")
                # emits a queue.Empty exception if the queue is empty for 0.01 seconds
                try:
                    subscriber.handle(item)
                except Exception as err:
                    # we need to handle every error so a simple error does not prevent future data from being handled.
                    warnings.warn(f"Subscriber {subscriber} failed to handle {item} with error {err}")
            except queue.Empty:
                continue

    def add_sub(self, subscriber: Subscriber[T]):
        """Adds a subscriber to the stream."""
        self._subscribers.append(subscriber)
        self._queues[subscriber] = queue.Queue()
        self._executor.submit(self._listener, subscriber)

    def stop(self, force: bool = False):
        """Turns off the stream so the subs don't handle any new data."""
        # if we are not forcing we should wait until the last data has opened a thread to
        if not force:
            # if there is currently unhandled data we should wait until every sub has picked it up.
            if self.is_unhandled:

                while self.is_unhandled:
                    # add a debounced checker to see if all outstanding changes have been addressed
                    time.sleep(0.05)
                    print(self.is_unhandled)

        self._running = False
        self._executor.shutdown(wait=not force)
        if not force:
            while self.is_unhandled:
                time.sleep(0.05)  # we want to debounce this a bit because it could be locking for repetitive access to
                # thread safe type.

        self._running = False
        self._executor.shutdown(wait=not force)


class NullConcreteSub(Subscriber):
    def handle(self, item: T) -> None:
        return None


@dataclass(frozen=True)
class RequestStreamData:
    """A parent class for types which are going to be streamed."""

    pass


@dataclass(frozen=True)
class LastRequestStream(RequestStreamData):
    """A unfinished class to handle the token-by-token streaming of the final response from the model."""

    stream: str
    disregard_previous: bool
