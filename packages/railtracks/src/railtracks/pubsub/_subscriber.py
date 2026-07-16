from __future__ import annotations

import asyncio
import warnings
from typing import Any, Callable, Mapping, Union

from .messages import RequestCompletionMessage, Streaming, StreamingKind


class BroadcastCallbackSubscriber:
    """
    Bus subscriber that drives a user callback (`broadcast_callback` or `stream_callback`).

    The two session-level callback lanes are separated by the traffic `kind` on each
    `Streaming` message:

    - `kind="event"`: one-off items published with `rt.broadcast` -> `broadcast_callback`.
    - `kind="stream"`: chunks of an `rt.broadcast_stream` production (LLM token streams
      included) -> `stream_callback`.

    Each subscriber instance filters to its own kind (or observes everything when
    `kind=None`). The callback itself takes one of two forms:

    - A single callable receives every matching item regardless of channel (the "firehose"
      form; prefer the mapping form to listen selectively).
    - A mapping routes each item to the callable registered under the item's channel name;
      items on channels without a registered callable are skipped silently.

    Callables may be sync or async.

    The subscriber tracks what it observed and delivered so `warn_if_unused()` can flag, at
    session close, a callback that never fired — the most common causes being a channel-name
    typo, listening on the wrong lane (events vs. stream chunks), or expecting LLM tokens
    from a run that never streamed (callbacks are passive; only `rt.astream` /
    `Flow.astream` enable streaming).
    """

    def __init__(
        self,
        callback: Union[
            Callable[[Any], Any],
            Mapping[str, Callable[[Any], Any]],
        ],
        *,
        kind: StreamingKind | None = None,
        param_name: str = "broadcast_callback",
    ):
        """
        Args:
            callback: The user callback (single callable or channel-name -> callable mapping).
            kind: The traffic kind this subscriber listens to (`"event"` / `"stream"`), or
                None to receive every `Streaming` item regardless of kind.
            param_name: The user-facing parameter this callback was registered as; used in
                `warn_if_unused` messages.
        """
        self._callback = callback
        self._kind = kind
        self._param_name = param_name
        self._items_seen = 0
        self._channels_seen: set[str] = set()
        # channels observed carrying the OTHER kind of traffic — used to hint at lane mix-ups
        self._offkind_channels: set[str] = set()
        self._fired_channels: set[str] = set()
        self._fired = False

    async def __call__(self, item: RequestCompletionMessage) -> None:
        """Handles one bus message: routes matching `Streaming` items to the user callback."""
        if not isinstance(item, Streaming):
            return

        if self._kind is not None and item.kind != self._kind:
            self._offkind_channels.add(item.channel)
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

    def _never_fired_hint(self) -> str:
        """The likely cause when zero matching items were observed, per lane."""
        if self._kind == "stream":
            hint = (
                "— nothing streamed during this session. Note that callbacks do not "
                "enable streaming; invoke with rt.astream / Flow.astream (optionally "
                ".route(...))."
            )
        elif self._kind == "event":
            hint = "— nothing was broadcast (rt.broadcast) during this session."
        else:
            hint = "— nothing was broadcast during this session."

        if self._offkind_channels:
            other = "event" if self._kind == "stream" else "stream"
            other_param = (
                "broadcast_callback" if other == "event" else "stream_callback"
            )
            hint += (
                f" However, channels {sorted(self._offkind_channels)} carried {other} "
                f"traffic — did you mean to register a {other_param}?"
            )
        return hint

    def warn_if_unused(self) -> None:
        """
        Emits a `UserWarning` when the callback (or some of its channel entries) never
        received an item over the subscriber's lifetime. Called by the session at close.
        (A `UserWarning` — not a log record — so it is visible by default, without
        `enable_logging()`.)

        The message distinguishes the failure modes:
        - nothing matching was broadcast at all (likely: expected tokens without streaming,
          or the traffic went down the other callback lane), vs.
        - matching traffic existed but none was on the registered channels (likely: a
          channel-name typo).
        """
        if isinstance(self._callback, Mapping):
            registered = set(self._callback.keys())
            unused = registered - self._fired_channels
            if not unused:
                return
            if self._items_seen == 0:
                warnings.warn(
                    f"{self._param_name} channels {sorted(unused)} never received any "
                    f"items {self._never_fired_hint()}",
                    UserWarning,
                    stacklevel=2,
                )
            else:
                warnings.warn(
                    f"{self._param_name} channels {sorted(unused)} never received any "
                    f"items; observed channels were {sorted(self._channels_seen)} (check "
                    "for channel-name typos).",
                    UserWarning,
                    stacklevel=2,
                )
        elif not self._fired:
            warnings.warn(
                f"{self._param_name} was registered but never received any items "
                f"{self._never_fired_hint()}",
                UserWarning,
                stacklevel=2,
            )
