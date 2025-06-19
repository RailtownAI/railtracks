# from .exception_messages import get_message, get_notes
from ..errors import NodeInvocationError
from ...llm import Message, MessageHistory, ModelBase, SystemMessage
import warnings


def check_message_history(
    message_history: MessageHistory, system_message: SystemMessage = None
) -> None:
    if any(not isinstance(m, Message) for m in message_history):
        raise NodeInvocationError(
            message="Message history must be a list of Message objects",
            notes=[
                "System messages must be of type rc.llm.SystemMessage (not string)",
                "User messages must be of type rc.llm.UserMessage (not string)",
            ],
            fatal=True,
        )
    elif len(message_history) == 0 and system_message is None:
        raise NodeInvocationError(
            message="Message history must contain at least one message",
            notes=["Please provide an initial message"],
            fatal=True,
        )
    elif (
        len(message_history) > 0
        and message_history[0].role != "system"
        and not system_message
    ):
        warnings.warn(
            "No SystemMessage was provided. This is not recommended. Please provide the first message as a SystemMessage."
        )
    elif (len(message_history) == 1 and message_history[0].role == "system") or (
        system_message and len(message_history) == 0
    ):
        warnings.warn(
            "Only SystemMessage was provided. This is not recommended. Please provide at least one UserMessage."
        )


def check_model(model: ModelBase):
    if model is None:
        raise NodeInvocationError(
            message="You must provide a model to this node.",
            notes=[
                "You can provide the model during the time of node creation using easy_usage_wrappers. \nEg:\n_ = rc.library.terminal_llm(..., model=rc.llm.OpenAILLM('gpt-4o'))",
                "You can insert the model during the time of node invocation using the 'model' parameter. \nEg:\n_ = rc.call(node, model=rc.llm.OpenAILLM('gpt-4o'))",
            ],
            fatal=True,
        )
