from __future__ import annotations

import asyncio
from typing import Any

from typing_extensions import Never

from railtracks.middleware.core import Middleware


class Lock(Middleware[Any, Any, Never]):
    """Serialize concurrent invocations of the wrapped call.

    Reuse one instance across nodes that must not execute concurrently.
    """

    def __init__(self):
        self._lock = asyncio.Lock()
        super().__init__(self._middleware_fn)

    async def _middleware_fn(self, call, *args, **kwargs):
        async with self._lock:
            return await call(*args, **kwargs)
