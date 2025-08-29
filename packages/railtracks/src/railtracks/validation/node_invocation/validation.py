from railtracks.exceptions.errors import NodeInvocationError
from railtracks.exceptions.messages.exception_messages import (
    ExceptionMessageKey,
    get_message,
    get_notes,
)
from railtracks.llm import Message, MessageHistory, ModelBase
from railtracks.utils.logging import get_rt_logger

# Global logger for validation
logger = get_rt_logger("Validation")


def check_message_history(
    message_history: MessageHistory, system_message: str | None = None
) -> None:
    if any(not isinstance(m, Message) for m in message_history):
        raise NodeInvocationError(
            message=get_message("MESSAGE_HISTORY_TYPE_MSG"),
            notes=get_notes("MESSAGE_HISTORY_TYPE_NOTES"),
            fatal=True,
        )
    elif len(message_history) == 0 and system_message is None:
        raise NodeInvocationError(
            message=get_message("MESSAGE_HISTORY_EMPTY_MSG"),
            notes=get_notes("MESSAGE_HISTORY_EMPTY_NOTES"),
            fatal=True,
        )
    elif (
        len(message_history) > 0
        and message_history[0].role != "system"
        and not system_message
    ):
        logger.warning(get_message("NO_SYSTEM_MESSAGE_WARN"))
    elif (len(message_history) == 1 and message_history[0].role == "system") or (
        system_message and len(message_history) == 0
    ):
        logger.warning(get_message("ONLY_SYSTEM_MESSAGE_WARN"))


def check_llm_model(llm: ModelBase | None):
    if llm is None:
        raise NodeInvocationError(
            message=get_message("MODEL_REQUIRED_MSG"),
            notes=get_notes("MODEL_REQUIRED_NOTES"),
            fatal=True,
        )


def check_max_tool_calls(max_tool_calls: int | None):
    if max_tool_calls is None:
        logger.warning(get_message(ExceptionMessageKey.MAX_TOOL_CALLS_UNLIMITED_WARN))
    elif max_tool_calls < 0:
        raise NodeInvocationError(
            get_message(ExceptionMessageKey.MAX_TOOL_CALLS_NEGATIVE_MSG),
            notes=get_notes(ExceptionMessageKey.MAX_TOOL_CALLS_NEGATIVE_NOTES),
        )
