from railtracks.middleware.core import Middleware


class MaxCalls(Middleware):
    """Fail the wrapped call once it has been invoked ``max_calls`` times.

    Slot-agnostic: works both as node middleware (``middleware=``) and as model
    middleware (``model_middleware=``) — it only counts invocations of ``call``
    and never inspects the arguments::

        import railtracks as rt
        from railtracks.prebuilt import middleware

        rt.agent_node(
            "Agent",
            llm=rt.llm.OpenAILLM(model_name="gpt-4o"),
            middleware=[middleware.MaxCalls(5)],  # cap calls to the whole node
            model_middleware=[middleware.MaxCalls(5)],  # cap raw model calls
        )

    The count is tracked per ``MaxCalls`` instance, so a single instance shared
    across nodes enforces a combined budget, while a fresh instance per node
    gives each its own limit.

    Args:
        max_calls: Number of calls allowed before the limit is enforced.
        custom_message: Message to raise once the limit is exceeded. Defaults
            to ``"Maximum number of calls exceeded"``.
    """

    def __init__(self, max_calls: int, custom_message: str | None = None):
        self._max_calls = max_calls
        self._call_count = 0
        self._custom_message = custom_message
        super().__init__(self._middleware_fn)

    async def _middleware_fn(self, call, *args, **kwargs):
        if self._call_count >= self._max_calls:
            if self._custom_message:
                raise Exception(self._custom_message)
            raise Exception("Maximum number of calls exceeded")
        self._call_count += 1
        return await call(*args, **kwargs)
