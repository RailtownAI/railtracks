from __future__ import annotations

import asyncio

from railtracks.middleware.core import Middleware


class Timeout(Middleware):
    """Fail the wrapped call when it runs longer than ``seconds``.

    The timeout applies to the complete wrapped call. When the deadline expires,
    the call is cancelled and :class:`TimeoutError` is raised.

    Args:
        seconds: Maximum number of seconds to wait for the wrapped call.
    """

    def __init__(self, seconds: float):
        self._seconds = seconds
        super().__init__(self._middleware_fn)

    async def _middleware_fn(self, call, *args, **kwargs):
        return await asyncio.wait_for(call(*args, **kwargs), timeout=self._seconds)
