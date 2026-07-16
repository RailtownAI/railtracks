from __future__ import annotations

import asyncio
from typing import Any, Callable, Mapping, Union

from railtracks.utils.logging import get_rt_logger

from .messages import RequestCompletionMessage, Streaming

logger = get_rt_logger(__name__)


class BroadcastCallbackSubscriber:
    """
    Bus subscriber that drives a user `broadcast_callback`.

    - A single callable receives every streamed/broadcast item regardless of channel (the
      "firehose" form — note this includes token chunks whenever something in the session
      streams; prefer the mapping form to listen selectively).
    - A mapping routes each item to the callable registered under the item's channel name;
      items on channels without a registered callable are skipped silently.

    Callables may be sync or async.

    The subscriber tracks what it observed and delivered so `warn_if_unused()` can flag, at
    session close, a callback that never fired — the most common causes being a channel-name
    typo, or expecting LLM tokens from a run that never streamed (callbacks are passive; only
    `rt.astream` / `Flow.astream` enable streaming).
    """

    def __init__(
        self,
        callback: Union[
            Callable[[Any], Any],
            Mapping[str, Callable[[Any], Any]],
        ],
    ):
        self._callback = callback
        self._items_seen = 0
        self._channels_seen: set[str] = set()
        self._fired_channels: set[str] = set()
        self._fired = False

    async def __call__(self, item: RequestCompletionMessage) -> None:
        """Handles one bus message: routes `Streaming` items to the user callback."""
        if not isinstance(item, Streaming):
            return

        self._items_seen += 1
        self._channels_seen.add(item.channel)

        if isinstance(self._callback, Mapping):
            fn = self._callback.get(item.channel)
            if fn is None:
                return
            self._fired_channels.add(item.channel)
        else:
            fn = self._callback
        self._fired = True

        result = fn(item.streamed_object)
        if asyncio.iscoroutine(result):
            await result

    def warn_if_unused(self) -> None:
        """
        Logs a warning when the callback (or some of its channel entries) never received an
        item over the subscriber's lifetime. Called by the session at close.

        The message distinguishes the two failure modes:
        - nothing was broadcast at all (likely: expected tokens but nothing streamed), vs.
        - traffic existed but none matched the registered channels (likely: a channel typo).
        """
        if isinstance(self._callback, Mapping):
            registered = set(self._callback.keys())
            unused = registered - self._fired_channels
            if not unused:
                return
            if self._items_seen == 0:
                logger.warning(
                    "broadcast_callback channels %s never received any items — nothing was "
                    "broadcast during this session. If you expected LLM tokens, note that "
                    "callbacks do not enable streaming; invoke with rt.astream / Flow.astream "
                    "(optionally .route(...)).",
                    sorted(unused),
                )
            else:
                logger.warning(
                    "broadcast_callback channels %s never received any items; observed "
                    "channels were %s (check for channel-name typos).",
                    sorted(unused),
                    sorted(self._channels_seen),
                )
        elif not self._fired:
            logger.warning(
                "broadcast_callback was registered but never received any items — nothing "
                "was broadcast during this session. If you expected LLM tokens, note that "
                "callbacks do not enable streaming; invoke with rt.astream / Flow.astream "
                "(optionally .route(...))."
            )
