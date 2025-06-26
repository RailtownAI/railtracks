import string
import requestcompletion as rc
from requestcompletion.exceptions import ContextError
from ..context.central import get_local_config
from ..llm import MessageHistory, Message


class KeyOnlyFormatter(string.Formatter):
    def get_value(self, key, args, kwargs):
        try:
            return kwargs[str(key)]
        except KeyError:
            return f"{{{key}}}"


class _ContextDict(dict):
    def __getitem__(self, key):
        return rc.context.get(key)

    def __missing__(self, key):
        return f"{{{key}}}"  # Return the placeholder if not found


def fill_prompt(prompt: str) -> str:
    return KeyOnlyFormatter().vformat(prompt, (), _ContextDict())


def inject_context(message_history: MessageHistory):
    """
    Injects the context from the current request into the prompt.

    Args:
        message_history (MessageHistory): The prompts to inject context into.

    """
    # we need to be able to handle the case where the user is not running this within the context of a `rc.Runner()`
    try:
        local_config = get_local_config()
        is_prompt_inject = local_config.prompt_injection
    except ContextError:
        is_prompt_inject = False

    if is_prompt_inject:
        for i, message in enumerate(message_history):
            if message.inject_prompt and isinstance(message.content, str):
                try:
                    message_history[i] = Message(
                        role=message.role.value,
                        content=fill_prompt(message.content),
                        inject_prompt=False,
                    )
                except ValueError:
                    pass

    return message_history
