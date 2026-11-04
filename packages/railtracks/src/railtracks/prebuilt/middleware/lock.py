from __future__ import annotations

import asyncio
import threading
from typing import Any

from typing_extensions import Never

from railtracks.middleware.core import Middleware


class Lock(Middleware[Any, Any, Never]):
    """Serialize concurrent invocations of the wrapped call.

    Reuse one instance across nodes that must not execute concurrently. Only
    calls on the same event loop are serialized. Each sync ``flow.invoke()``
    runs on its own loop, so two ``invoke()`` calls running at the same time on
    different threads are not serialized against each other.
    """

    def __init__(self):
        # an asyncio.Lock binds to the first loop that waits on it
        self._locks: dict[asyncio.AbstractEventLoop, asyncio.Lock] = {}
        self._locks_guard = threading.Lock()
        super().__init__(self._middleware_fn)

    def _lock_for_running_loop(self) -> asyncio.Lock:
        loop = asyncio.get_running_loop()
        with self._locks_guard:
            lock = self._locks.get(loop)
            if lock is None:
                for closed in [other for other in self._locks if other.is_closed()]:
                    del self._locks[closed]
                lock = self._locks[loop] = asyncio.Lock()
            return lock

    async def _middleware_fn(self, call, *args, **kwargs):
        async with self._lock_for_running_loop():
            return await call(*args, **kwargs)
