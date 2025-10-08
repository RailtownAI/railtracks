from railtracks.llm import UserMessage, SystemMessage, MessageHistory
from railtracks.llm.prompt_injection_utils import ValueDict

def inject_values(message_history: MessageHistory, value_dict: ValueDict):
    """
    Injects the values in the `value_dict` from the current request into the prompt.

    Args:
        message_history (MessageHistory): The prompts to inject context into.
        value_dict (ValueDict): The dictionary containing values to fill in the prompt.

    """

    for message in message_history:
        if message.inject_prompt and isinstance(message.content, str):
            try:
                if isinstance(message, (UserMessage, SystemMessage)):
                    message.fill_prompt(value_dict)
            except ValueError:
                pass

    return message_history
