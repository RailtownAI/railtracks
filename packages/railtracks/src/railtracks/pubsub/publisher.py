from __future__ import annotations

from railtracks.utils.logging import get_rt_logger
from railtracks.utils.logging.config import LIFECYCLE_EXTRA
from railtracks.utils.publisher import Publisher

from .messages import (
    RequestCompletionMessage,
    RequestCreation,
    RequestCreationFailure,
    RequestFailure,
    RequestSuccess,
)

logger = get_rt_logger(__name__)


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
        # the run view already prints node starts, results, and failures
        extra = (
            LIFECYCLE_EXTRA
            if isinstance(message, (RequestCreation, RequestSuccess, RequestFailure))
            else None
        )
        if isinstance(message, (RequestCreationFailure, RequestFailure)):
            logger.debug(message.log_message(), exc_info=message.error, extra=extra)
        else:
            logger.debug(message.log_message(), extra=extra)
