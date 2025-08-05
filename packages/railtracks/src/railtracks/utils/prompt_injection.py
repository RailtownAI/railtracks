import string

from railtracks.llm import Message, MessageHistory


class KeyOnlyFormatter(string.Formatter):
    """
    A simple formatter which will only use keyword arguments to fill placeholders.
    """

    def get_value(self, key, args, kwargs):
        try:
            return kwargs[str(key)]
        except KeyError:
            return f"{{{key}}}"


class ValueDict(dict):
    def __missing__(self, key):
        return f"{{{key}}}"  # Return the placeholder if not found


def fill_prompt(prompt: str, value_dict: ValueDict) -> str:
    """
    Fills a prompt using the railtracks context object as its source of truth
    """
    return KeyOnlyFormatter().vformat(prompt, (), value_dict)


def inject_values(message_history: MessageHistory, value_dict: ValueDict):
    """
    Injects the values in the `value_dict` from the current request into the prompt.

    Args:
        message_history (MessageHistory): The prompts to inject context into.
        value_dict (ValueDict): The dictionary containing values to fill in the prompt.

    """

    for i, message in enumerate(message_history):
        if message.inject_prompt and isinstance(message.content, str):
            try:
                message_history[i] = Message(
                    role=message.role.value,
                    content=fill_prompt(message.content, value_dict),
                    inject_prompt=False,
                )
            except ValueError:
                pass

    return message_history
