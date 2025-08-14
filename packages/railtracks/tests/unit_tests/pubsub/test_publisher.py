import pytest
import asyncio
from railtracks.utils.publisher import Subscriber
from railtracks.pubsub.messages import RequestCompletionMessage


@pytest.mark.asyncio
async def test_rcpublisher_logging_sub(dummy_publisher):
    # Should have one default broadcast_callback (logging_sub)
    assert len(dummy_publisher._subscribers) >= 1
    msg = RequestCompletionMessage()
    dummy_publisher._running = True
    dummy_publisher._queue = asyncio.Queue()
    await dummy_publisher.publish(msg)
    assert await dummy_publisher._queue.get() == msg

@pytest.mark.asyncio
async def test_subscriber_trigger_handles_exception(logger_patch):
    def bad_callback(x):
        raise Exception("fail!")

    sub = Subscriber(bad_callback)
    await sub.trigger(1)
    # Ensure debug was called at least once
    assert logger_patch.debug.called

