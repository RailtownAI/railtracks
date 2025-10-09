from __future__ import annotations

import asyncio
import uuid
from typing import Callable, Coroutine, Generic, List, TypeVar

from .logging.create import get_rt_logger

_T = TypeVar("_T")
_TOutput = TypeVar("_TOutput")

logger = get_rt_logger("Publisher")


class Subscriber(Generic[_T]):
    """A simple wrapper class of a callback function."""

    # this could be done without a class, but I want to keep as extendable as possible.
    def __init__(
        self,
        callback: Callable[[_T], None] | Callable[[_T], Coroutine[None, None, None]],
        name: str | None = None,
    ):
        self.callback = callback
        self.name = name if name is not None else callback.__name__
        self.id = str(uuid.uuid4())

    async def trigger(self, message: _T):
        """Trigger this broadcast_callback with the given message."""
        try:
            result = self.callback(message)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            logger.debug(msg=f"Error in {self.name}", exc_info=e)


class Publisher(Generic[_T]):
    """
    A simple publisher object with some basic functionality to publish and suvbscribe to messages.

    Note a couple of things:
    - Message will be handled in the order they came in (no jumping the line)
    - If you add a broadcast_callback during the operation it will handle any new messages that come in after the subscription
        took place
    - Calling the shutdown method will kill the publisher forever. You will have to make a new one after.
    """

    timeout = 0.001

    def __init__(
        self,
    ):
        self._queue: asyncio.Queue[_T] | None = None
        self._subscribers: List[Subscriber[_T]] = []

        self._running = False

        self.pub_loop = None

    async def __aenter__(self):
        """Enable the use of the publisher in a context manager."""
        await self.start()
        return self

    async def start(self):
        # you must set the kill variables first or the publisher loop will early exit.
        self._running = True
        self._queue = asyncio.Queue()
        self.pub_loop = asyncio.create_task(
            self._published_data_loop(), name="Publisher Loop"
        )

    async def __aexit__(self, exc_type, exc_value, traceback):
        """Shutdown the publisher when exiting the context manager."""
        await self.shutdown()

    async def publish(self, message: _T):
        """Publish a message the publisher. This will trigger all subscribers to receive the message.

        Args:
            message: The message you would like to publish.

        """
        # logger.debug(f"Publishing message: {message}")
        if not self._running:
            raise RuntimeError("Publisher is not currently running.")

        await self._queue.put(message)

    async def _published_data_loop(self):
        """
        A loop designed to be run in a thread that will continuously check for new messages in the queue and trigger
        subscribers as they are received
        """
        while self._running:
            try:
                message = await asyncio.wait_for(
                    self._queue.get(), timeout=self.timeout
                )

                try:
                    contracts = [sub.trigger(message) for sub in self._subscribers]

                    await asyncio.gather(*contracts)

                # we need a broad exception clause to catch any errors that might occur in the subs.
                except Exception:
                    pass

                # will only reach this section after all the messages have been handled

            # this exception is raised when the queue is empty for `self.timeout` seconds.
            # we do this so we can check is the self._running flag.
            except asyncio.TimeoutError:
                continue

    def subscribe(
        self,
        callback: Callable[[_T], None] | Callable[[_T], Coroutine[None, None, None]],
        name: str | None = None,
    ) -> str:
        """
        Subscribe the publisher so whenever we receive a message the callback will be triggered.

        Args:
            callback: The callback function that will be triggered when a message is published.
            name: Optional name for the broadcast_callback, mainly used for debugging.

        Returns:
            str: A unique identifier for the broadcast_callback. You can use this key to unsubscribe later.

        """
        sub = Subscriber(callback, name)
        self._subscribers.append(sub)
        return sub.id

    def unsubscribe(self, identifier: str):
        """
        Unsubscribe the publisher so the given broadcast_callback will no longer receive messages.

        Args:
            identifier: The unique identifier of the broadcast_callback to remove.

        Raises:
            KeyError: If no broadcast_callback with the given identifier exists.
        """
        index_to_remove = [
            index for index, sub in enumerate(self._subscribers) if sub.id == identifier
        ]
        if not index_to_remove:
            raise KeyError(f"No broadcast_callback with identifier {identifier} found.")

        index_to_remove = index_to_remove[0]
        self._subscribers.pop(index_to_remove)

    async def listener(
        self,
        message_filter: Callable[[_T], bool],
        result_mapping: Callable[[_T], _TOutput] = lambda x: x,
        listener_name: str | None = None,
    ):
        """
        Creates a special listener object that will wait for the first message that matches the given filter.

        After receiving the message it will run the result_mapping function on the message and return the result, and
        kill the broadcast_callback.

        Args:
            message_filter: A function that takes a message and returns True if the message should be returned.
            result_mapping: A function that maps the message into a final result.
            listener_name: Optional name for the listener, mainly used for debugging.
        """

        async def single_listener():
            returnable_result: asyncio.Future[_T] = asyncio.Future()
            # we are gonna use the asyncio.event system instead of threading
            listener_event = asyncio.Event()

            async def special_subscriber(message: _T):
                nonlocal returnable_result
                if message_filter(message):
                    # this will trigger the end of the listener loop
                    returnable_result.set_result(message)
                    listener_event.set()
                    return

            sub_id = self.subscribe(
                callback=special_subscriber,
                name=listener_name,
            )

            while True:
                try:
                    await asyncio.wait_for(listener_event.wait(), timeout=self.timeout)
                    break
                except asyncio.TimeoutError:
                    pass

                if not self._running:
                    raise ValueError(
                        "Listener has been killed before receiving the correct message."
                    )

            unwrapped_returned_result: _T = returnable_result.result()
            self.unsubscribe(sub_id)
            return result_mapping(unwrapped_returned_result)

        return await single_listener()

    async def shutdown(self):
        """
        Shutdowns the publisher and halts the listener loop.

        Note that this will work slowly, as it will wait for the current messages in the queue to be processed before
        shutting down.
        """

        self._running = False
        await self.pub_loop

        return

    def is_running(self) -> bool:
        """
        Check if the publisher is currently running.

        Returns:
            bool: True if the publisher is running, False otherwise.
        """
        return self._running
