from railtracks.exceptions.errors import NodeInvocationError
from railtracks.exceptions.messages.exception_messages import (
    get_message,
    get_notes,
)
from railtracks.llm import Message, MessageHistory, ModelBase
from railtracks.llm.message import Role
from railtracks.utils.logging import get_rt_logger

# Global logger for validation
logger = get_rt_logger(__name__)


def check_message_history(message_history: MessageHistory) -> None:
    """Validate a prepared message history and warn about shapes models handle poorly.

    Expects the history as it will be sent to the model, with the agent's own system message
    already in place.

    Args:
        message_history: The prepared history to check.

    Raises:
        NodeInvocationError: If the history holds something other than Message objects, or if it
            is empty.
    """
    if any(not isinstance(m, Message) for m in message_history):
        raise NodeInvocationError(
            message=get_message("MESSAGE_HISTORY_TYPE_MSG"),
            notes=get_notes("MESSAGE_HISTORY_TYPE_NOTES"),
            fatal=True,
        )

    if len(message_history) == 0:
        raise NodeInvocationError(
            message=get_message("MESSAGE_HISTORY_EMPTY_MSG"),
            notes=get_notes("MESSAGE_HISTORY_EMPTY_NOTES"),
            fatal=True,
        )

    system_count = sum(1 for m in message_history if m.role == Role.system)
    leading_system_count = 0
    for message in message_history:
        if message.role != Role.system:
            break
        leading_system_count += 1

    if system_count == 0:
        logger.warning(get_message("NO_SYSTEM_MESSAGE_WARN"))
    elif system_count == len(message_history):
        logger.warning(get_message("ONLY_SYSTEM_MESSAGE_WARN"))
    elif system_count > leading_system_count:
        logger.warning(get_message("MID_CONVERSATION_SYSTEM_WARN"))


def check_llm_model(llm: ModelBase | None):
    if llm is None:
        raise NodeInvocationError(
            message=get_message("MODEL_REQUIRED_MSG"),
            notes=get_notes("MODEL_REQUIRED_NOTES"),
            fatal=True,
        )
