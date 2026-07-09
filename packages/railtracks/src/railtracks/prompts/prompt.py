from typing import Awaitable, Callable


from pydantic import BaseModel

import railtracks.context as context
from railtracks.context.central import get_local_config
from railtracks.exceptions import ContextError
from railtracks.llm import MessageHistory
from railtracks.llm.response import Response
from railtracks.llm.tools.tool import Tool
from railtracks.middleware import gate
from railtracks.middleware.primitives import wrapper
from railtracks.utils.prompt_injection import ValueDict, inject_values


class _ContextDict(ValueDict):
    def __getitem__(self, key):
        return context.get(key)


def inject_context(message_history: MessageHistory):
    """
    Injects the context from the current request into the prompt.

    Args:
        message_history (MessageHistory): The prompts to inject context into.

    """
    # we need to be able to handle the case where the user is not running this within the context of a `rt.Session()`
    try:
        # if the context is not set (Session is not active), the `ContextError` will be raised.
        local_config = get_local_config()
        is_prompt_inject = local_config.prompt_injection
    except ContextError:
        is_prompt_inject = False

    if is_prompt_inject:
        inject_values(message_history, _ContextDict())

    return message_history


@wrapper
async def context_injection_wrapper(
    call: Callable[
        [MessageHistory, type[BaseModel] | None, list[Tool] | None], Awaitable[Response]
    ],
    message_history: MessageHistory,
    schema: type[BaseModel] | None,
    tools: list[Tool] | None,
):
    """
    
    """
    inject_context(message_history)

    return await call(message_history, schema, tools)
