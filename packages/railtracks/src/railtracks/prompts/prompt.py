import railtracks.context as context
from railtracks.llm import MessageHistory
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
    return inject_values(message_history, _ContextDict())
