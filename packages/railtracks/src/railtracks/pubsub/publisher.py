from __future__ import annotations

from railtracks.utils.publisher import Publisher

from .messages import RequestCompletionMessage


class RTPublisher(Publisher[RequestCompletionMessage]):
    """
    A specialized Publisher class designed to handle RequestCompletionMessage objects.
    """
