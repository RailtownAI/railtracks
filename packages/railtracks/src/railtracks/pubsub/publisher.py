from __future__ import annotations

from railtracks.utils.logging import get_rt_logger
from railtracks.utils.publisher import Publisher

from .messages import RequestCompletionMessage, RequestCreationFailure, RequestFailure

logger = get_rt_logger("Publisher")


class RTPublisher(Publisher[RequestCompletionMessage]):
    """
    A specialized Publisher class designed to handle RequestCompletionMessage objects.
    """

    def __init__(self):
        super().__init__()
        self.subscribe(self.logging_sub)

    @classmethod
    async def logging_sub(cls, message: RequestCompletionMessage):
        """
        Logs the provided message as a debug message.

        In the case that we see an error that is also logged.
        """
        if isinstance(message, (RequestCreationFailure, RequestFailure)):
            logger.debug(message.log_message(), exc_info=message.error)
        else:
            logger.debug(message.log_message())
