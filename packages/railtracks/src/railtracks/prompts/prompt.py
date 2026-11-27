from typing import Any

from railtracks.context.central import safe_get_runner_context
from railtracks.llm import MessageHistory
from railtracks.utils.context_injection import ValueDict, inject_values


class _ContextDict(ValueDict):
    def __init__(self) -> None:
        super().__init__()
        self._snapshot: dict[str, Any] | None = None

    def __getitem__(self, key: str) -> Any:
        if self._snapshot is None:
            self._snapshot = dict(safe_get_runner_context().external_context.items())
        return self._snapshot[key]


def inject_context(message_history: MessageHistory):
    """
    Injects the context from the current request into the prompt.

    Args:
        message_history (MessageHistory): The prompts to inject context into.

    """
    return inject_values(message_history, _ContextDict())
