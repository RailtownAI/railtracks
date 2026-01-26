import pytest
import asyncio
from railtracks.utils.publisher import Subscriber
from railtracks.pubsub.messages import RequestCompletionMessage
from railtracks.utils.publisher import Publisher

class DummyMessage:
    def __init__(self, value):
        self.value = value


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



@pytest.mark.asyncio
async def test_publisher_drains_queue_on_shutdown():
    pub = Publisher()
    await pub.start()
    results = []

    def cb(msg):
        results.append(msg.value)

    pub.subscribe(cb)

    # publish some messages
    for i in range(5):
        await pub.publish(DummyMessage(i))

    await pub.shutdown()  # should process all 5

    # All messages delivered
    assert sorted(results) == list(range(5))
    assert not pub.is_running()

@pytest.mark.asyncio
async def test_publisher_no_new_publishes_after_shutdown_requested():
    pub = Publisher()
    await pub.start()
    await pub.shutdown()
    with pytest.raises(RuntimeError, match="Publisher is not currently running"):
        await pub.publish(DummyMessage("after"))

@pytest.mark.asyncio
async def test_shutdown_with_no_messages_is_clean():
    pub = Publisher()
    await pub.start()
    await pub.shutdown()
    assert not pub.is_running()

@pytest.mark.asyncio
async def test_listener_raises_on_premature_shutdown():
    pub = Publisher()
    await pub.start()
    # Force publisher to shutdown before any message matches
    # This will test the "Listener has been killed..." branch
    async def auto_shutdown():
        await asyncio.sleep(0.01)
        await pub.shutdown()
    shut_task = asyncio.create_task(auto_shutdown())
    with pytest.raises(ValueError, match="Listener has been killed"):
        await pub.listener(lambda m: False)
    await shut_task
