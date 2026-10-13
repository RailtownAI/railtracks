"""Close litellm's cached decisions client before its event loop closes.

``litellm.adecisions`` takes no client: it reuses one async httpx client per provider
and event loop from ``litellm.in_memory_llm_clients_cache``. Every ``asyncio.run``
(each ``Flow.invoke``) is a new loop, so each leaves a client with open TLS
connections behind; when those are garbage collected after their loop has closed,
asyncio prints "Fatal error on SSL transport ... Event loop is closed".

``close_client_on_loop_shutdown`` parks an async generator in the running loop.
``asyncio.run`` closes a loop's async generators before closing the loop, which runs
the generator's ``finally``: it closes the loop's client there and evicts it, so the
connections shut down while their loop is still alive. Calls in the same loop keep
reusing the client until then. A loop closed without ``shutdown_asyncgens`` skips
the cleanup, which is no worse than not having it.
"""

from __future__ import annotations

import asyncio
import weakref
from collections.abc import AsyncGenerator

import litellm

# The key ``get_async_httpx_client(llm_provider=...)`` caches under, before litellm
# appends the event loop's id (litellm 1.104.2).
_CLIENT_KEY = "async_httpx_client"

_watchers: weakref.WeakKeyDictionary[
    asyncio.AbstractEventLoop, dict[str, AsyncGenerator[None, None]]
] = weakref.WeakKeyDictionary()


async def _close_at_shutdown(provider: str) -> AsyncGenerator[None, None]:
    try:
        yield
    finally:
        cache = litellm.in_memory_llm_clients_cache
        handler = cache.get_cache(_CLIENT_KEY + provider)
        if handler is not None:
            try:
                await handler.close()
            finally:
                cache.delete_cache(
                    cache.update_cache_key_with_event_loop(_CLIENT_KEY + provider)
                )


async def close_client_on_loop_shutdown(provider: str) -> None:
    """Have ``provider``'s cached client closed when the running loop shuts down."""
    loop = asyncio.get_running_loop()
    watchers = _watchers.setdefault(loop, {})
    if provider in watchers:
        return
    watcher = _close_at_shutdown(provider)
    await watcher.__anext__()  # starts it, so the loop tracks it until shutdown
    # the loop tracks async generators weakly; this keeps it alive until then
    watchers[provider] = watcher
