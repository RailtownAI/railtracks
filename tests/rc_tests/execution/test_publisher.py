import concurrent.futures
import time
import pytest
import asyncio

from requestcompletion.pubsub.publisher import Subscriber, Publisher


@pytest.mark.asyncio
async def test_basic_sub():
    number = None

    def callback(n: int):
        nonlocal number
        number = n

    sub = Subscriber(callback)

    assert sub.callback == callback

    await sub.trigger(42)

    assert number == 42


@pytest.mark.asyncio
async def test_sleep_sub():
    text = None

    def callback(t: str):
        nonlocal text
        time.sleep(0.2)
        text = t

    sub = Subscriber(callback)
    assert sub.callback == callback
    await sub.trigger("Hello, World!")
    assert text == "Hello, World!"


@pytest.mark.timeout(0.5)
@pytest.mark.asyncio
async def test_basic_publisher_without_context():
    publisher = Publisher()
    await publisher.start()
    _message = None

    def callback(message: str):
        nonlocal _message
        _message = message

    publisher.subscribe(callback)
    await publisher.publish("hello world")

    while _message is None:
        await asyncio.sleep(0.001)

    assert _message == "hello world"

    await publisher.shutdown()


@pytest.mark.timeout(0.5)
@pytest.mark.asyncio
async def test_basic_publisher():
    async with Publisher() as publisher:
        _message = None

        def callback(message: str):
            nonlocal _message
            _message = message

        publisher.subscribe(callback)
        await publisher.publish("hello world")

        while _message is None:
            await asyncio.sleep(0.000001)

        assert _message == "hello world"


@pytest.mark.timeout(0.5)
async def test_many_publishers():
    async with Publisher() as publisher:
        _message_1 = None
        _message_2 = None

        def callback1(message: str):
            nonlocal _message_1
            _message_1 = message

        def callback2(message: str):
            nonlocal _message_2
            _message_2 = message

        publisher.subscribe(callback1)
        publisher.subscribe(callback2)
        await publisher.publish("hello world")

        while _message_1 is None and _message_2 is None:
            await asyncio.sleep(0.000001)

        assert _message_1 == "hello world"
        assert _message_2 == "hello world"


@pytest.mark.timeout(1)
async def test_blocking_publisher():
    async with Publisher() as publisher:
        _message = []

        async def callback(message: str):
            nonlocal _message
            await asyncio.sleep(0.1)
            _message.append((time.time(), message))

        publisher.subscribe(callback)
        await publisher.publish("hello world")
        await publisher.publish("second")

        while len(_message) < 2:
            await asyncio.sleep(0.000001)

        assert _message[0][1] == "hello world"
        assert _message[1][1] == "second"
        assert _message[0][0] < _message[1][0], "Messages should be processed in order."
        assert (
            abs(_message[1][0] - _message[0][0] - 0.1) < 0.02
        ), "Messages should be processed with a delay of 0.1 seconds roughly"


@pytest.mark.asyncio
async def test_multiple_subs_with_blocking():
    async with Publisher() as publisher:
        _message_1 = []
        _message_2 = []

        async def callback1(message: str):
            nonlocal _message_1
            await asyncio.sleep(0.1)
            _message_1.append((time.time(), message))

        async def callback2(message: str):
            nonlocal _message_2
            _message_2.append((time.time(), message))

        publisher.subscribe(callback1)
        publisher.subscribe(callback2)
        await publisher.publish("hello world")
        await publisher.publish("second")

        while len(_message_1) < 2 or len(_message_2) < 2:
            await asyncio.sleep(0.000001)

        assert (
            abs(_message_1[0][0] - _message_2[0][0] - 0.1) < 0.02
        ), "Messages should be processed with a delay of 0.1 seconds roughly"
        assert (
            abs(_message_2[1][0] - _message_2[0][0] - 0.1) < 0.02
        ), "Second message should be delayed because of the other blocking operation"


@pytest.mark.asyncio
async def test_unsubscribe():
    async with Publisher() as publisher:
        _message = None

        def callback(message: str):
            nonlocal _message
            _message = message

        identifier = publisher.subscribe(callback)
        await publisher.publish("hello world")

        while _message is None:
            await asyncio.sleep(0.000001)

        assert _message == "hello world"

        publisher.unsubscribe(identifier)
        _message = None
        publisher.publish("this should not be received")

        time.sleep(0.1)  # Give some time to process the message

        assert _message is None, "Unsubscribed subscriber should not receive messages."


@pytest.mark.asyncio
async def test_bad_unsubscribe():
    async with Publisher() as publisher:
        with pytest.raises(KeyError):
            # Attempting to unsubscribe a non-existent subscriber should raise KeyError
            publisher.unsubscribe("nonexistent_id")


@pytest.mark.asyncio
async def test_bad_subscribe():
    async with Publisher() as publisher:

        async def sample_sub(message: str):
            pass

        publisher.subscribe(sample_sub)
        with pytest.raises(KeyError):
            publisher.unsubscribe("not_a_callable")


@pytest.mark.asyncio
async def test_exception_thrower():
    async with Publisher() as publisher:

        def exception_thrower(message: str):
            raise ValueError("This is a test exception")

        _message = None

        def callback(message: str):
            nonlocal _message
            _message = message

        publisher.subscribe(callback)
        publisher.subscribe(exception_thrower)

        await publisher.publish("hello world")

        await publisher.publish("another message")

        await asyncio.sleep(0.1)
        assert (
            _message == "another message"
        ), "Callback should still receive messages even if one subscriber throws an exception"


@pytest.mark.asyncio
async def test_listener_simple():
    async with Publisher() as publisher:
        _message = None

        def callback(message: str):
            nonlocal _message
            _message = message

        publisher.subscribe(callback)

        def message_filter(message: str) -> bool:
            return message == "hello world"

        future = publisher.listener(message_filter)

        await publisher.publish("hello world")
        result = await future

        assert result == "hello world"
        assert _message == "hello world"


@pytest.mark.timeout(0.1)
@pytest.mark.asyncio
async def test_listener_many_messages():
    async with Publisher() as pub:
        hw_listener = pub.listener(lambda x: x == "hello world")

        am_listener = pub.listener(lambda x: x == "another message")

        await pub.publish("lala")
        await pub.publish("hello world")
        assert await hw_listener == "hello world"
        await pub.publish("another message")
        assert await am_listener == "another message"
        await pub.publish("hello world")


@pytest.mark.asyncio
async def test_precheck_listener():
    async with Publisher() as pub:
        hw_listener = pub.listener(lambda x: x == "hello world")

        await pub.publish("lala")

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(hw_listener, timeout=0.1)


@pytest.mark.asyncio
async def test_get_listener_after_shutdown():
    async with Publisher() as pub:
        hw_listener = pub.listener(lambda x: x == "hello world")

        await pub.publish("greenery")

    with pytest.raises(ValueError):
        await hw_listener  # Should raise an error since the publisher is shutdown
