import pytest
import asyncio
import time
from railtracks.utils.publisher import Publisher, Subscriber

from railtracks.pubsub._subscriber import stream_subscriber

# ================= START Subscriber class tests ============

class TestSubscriber:
    @pytest.mark.asyncio
    async def test_subscriber_stores_callback_and_name(self, sync_callback_container):
        _, callback = sync_callback_container
        sub = Subscriber(callback)
        assert sub.callback == callback
        assert sub.name == callback.__name__


    @pytest.mark.asyncio
    async def test_subscriber_custom_name(self, sync_callback_container):
        _, callback = sync_callback_container
        sub = Subscriber(callback, name="my_sub")
        assert sub.name == "my_sub"


    @pytest.mark.asyncio
    async def test_subscriber_trigger_sync(self, sync_callback_container):
        state, callback = sync_callback_container
        sub = Subscriber(callback)
        await sub.trigger(123)
        assert state["value"] == 123


    @pytest.mark.asyncio
    async def test_subscriber_trigger_async(self, async_callback_container):
        state, callback = async_callback_container
        sub = Subscriber(callback)
        await sub.trigger(555)
        assert state["value"] == 555


    @pytest.mark.asyncio
    async def test_basic_sub(self):
        number = None

        def callback(n: int):
            nonlocal number
            number = n

        sub = Subscriber(callback)

        assert sub.callback == callback

        await sub.trigger(42)

        assert number == 42


    @pytest.mark.asyncio
    async def test_sleep_sub(self):
        text = None

        def callback(t: str):
            nonlocal text
            time.sleep(0.2)
            text = t

        sub = Subscriber(callback)
        assert sub.callback == callback
        await sub.trigger("Hello, World!")
        assert text == "Hello, World!"
# ================ END Subscriber class tests ===============

# ================= START Publisher basic tests ============

class TestPublisher:
    @pytest.mark.asyncio
    async def test_basic_publisher_publish_sync(self, started_publisher, sync_callback_container):
        state, callback = sync_callback_container
        started_publisher.subscribe(callback)
        await started_publisher.publish("msg")
        for _ in range(10):
            if state["value"] == "msg":
                break
            await asyncio.sleep(0.01)
        assert state["value"] == "msg"


    @pytest.mark.asyncio
    async def test_basic_publisher_publish_async(
        self, started_publisher, async_callback_container
    ):
        state, callback = async_callback_container
        started_publisher.subscribe(callback)
        await started_publisher.publish(99)
        for _ in range(10):
            if state["value"] == 99:
                break
            await asyncio.sleep(0.01)
        assert state["value"] == 99


    @pytest.mark.asyncio
    async def test_publish_raises_if_not_started(self):
        pub = Publisher()
        with pytest.raises(RuntimeError):
            await pub.publish("fail")


    @pytest.mark.asyncio
    async def test_publisher_context_manager(self, async_publisher, sync_callback_container):
        state, callback = sync_callback_container
        async_publisher.subscribe(callback)
        await async_publisher.publish(999)
        for _ in range(10):
            if state["value"] == 999:
                break
            await asyncio.sleep(0.01)
        assert state["value"] == 999


    @pytest.mark.asyncio
    async def test_publisher_multiple_subscribers(self, started_publisher, msg_list_container):
        msgs, cb = msg_list_container
        another_msgs = []

        def cb2(m):
            another_msgs.append(m)

        started_publisher.subscribe(cb)
        started_publisher.subscribe(cb2)
        await started_publisher.publish("foo")
        await asyncio.sleep(0.01)
        assert "foo" in msgs
        assert "foo" in another_msgs


    @pytest.mark.timeout(0.5)
    @pytest.mark.asyncio
    async def test_basic_publisher_without_context(self):
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
    async def test_basic_publisher(self, started_publisher):
        _message = None

        def callback(message: str):
            nonlocal _message
            _message = message

        started_publisher.subscribe(callback)
        await started_publisher.publish("hello world")

        while _message is None:
            await asyncio.sleep(0.000001)

        assert _message == "hello world"
# ================ END Publisher basic tests ===============

# ================= START Subscriber list un/sub ============
class TestSubscriberList:
    @pytest.mark.asyncio
    async def test_unsubscribe_prevents_future_messages(self, started_publisher):
        received = []

        def cb(m):
            received.append(m)

        sid = started_publisher.subscribe(cb)
        await started_publisher.publish("one")
        await asyncio.sleep(0.01)
        started_publisher.unsubscribe(sid)
        await started_publisher.publish("two")
        await asyncio.sleep(0.01)
        assert received == ["one"]


    @pytest.mark.asyncio
    async def test_unsubscribe_missing_raises(self, started_publisher):
        with pytest.raises(KeyError):
            started_publisher.unsubscribe("nope")

    @pytest.mark.asyncio
    async def test_unsubscribe(self, started_publisher):
        _message = None

        def callback(message: str):
            nonlocal _message
            _message = message

        identifier = started_publisher.subscribe(callback)
        await started_publisher.publish("hello world")

        while _message is None:
            await asyncio.sleep(0.000001)

        assert _message == "hello world"

        started_publisher.unsubscribe(identifier)
        _message = None
        started_publisher.publish("this should not be received")

        time.sleep(0.1)  # Give some time to process the message

        assert _message is None, "Unsubscribed broadcast_callback should not receive messages."


    @pytest.mark.asyncio
    async def test_bad_unsubscribe(self, started_publisher):
        with pytest.raises(KeyError):
            # Attempting to unsubscribe a non-existent broadcast_callback should raise KeyError
            started_publisher.unsubscribe("nonexistent_id")


    @pytest.mark.asyncio
    async def test_bad_subscribe(self, started_publisher):

        async def sample_sub(message: str):
            pass

        started_publisher.subscribe(sample_sub)
        with pytest.raises(KeyError):
            started_publisher.unsubscribe("not_a_callable")
# ================ END Subscriber list un/sub ===============

# ================= START Publisher ordering/blocking tests ============

class TestPublisherOrdering:
    @pytest.mark.asyncio
    async def test_ordering_of_messages(self, async_publisher):
        received = []

        async def cb(m):
            await asyncio.sleep(0.01)
            received.append(m)

        async_publisher.subscribe(cb)
        await async_publisher.publish("first")
        await async_publisher.publish("second")
        for _ in range(20):
            if len(received) == 2:
                break
            await asyncio.sleep(0.01)
        assert received == ["first", "second"]


    @pytest.mark.asyncio
    async def test_mixed_sync_async_callbacks(self, async_publisher):
        received = []

        async def async_cb(x):
            received.append(f"async-{x}")

        def sync_cb(x):
            received.append(f"sync-{x}")

        async_publisher.subscribe(sync_cb)
        async_publisher.subscribe(async_cb)
        await async_publisher.publish("X")
        await asyncio.sleep(0.02)
        # Order is not guaranteed between sync/async
        assert set(received) == {"sync-X", "async-X"}


    @pytest.mark.asyncio
    async def test_callback_raises_does_not_block_others(self, started_publisher):
        got = []

        def good(m):
            got.append(m)

        def bad(m):
            raise Exception("Nope")

        started_publisher.subscribe(good)
        started_publisher.subscribe(bad)
        await started_publisher.publish("z")
        await asyncio.sleep(0.01)
        assert "z" in got


    @pytest.mark.timeout(1)
    async def test_blocking_publisher(self, started_publisher):
        _message = []

        async def callback(message: str):
            nonlocal _message
            await asyncio.sleep(0.1)
            _message.append((time.time(), message))

        started_publisher.subscribe(callback)
        await started_publisher.publish("hello world")
        await started_publisher.publish("second")

        while len(_message) < 2:
            await asyncio.sleep(0.000001)

        assert _message[0][1] == "hello world"
        assert _message[1][1] == "second"
        assert _message[0][0] < _message[1][0], "Messages should be processed in order."
        assert (
            abs(_message[1][0] - _message[0][0] - 0.1) < 0.02
        ), "Messages should be processed with a delay of 0.1 seconds roughly"


    @pytest.mark.asyncio
    async def test_multiple_subs_with_blocking(self, started_publisher):
        _message_1 = []
        _message_2 = []

        async def callback1(message: str):
            nonlocal _message_1
            await asyncio.sleep(0.1)
            _message_1.append((time.time(), message))

        async def callback2(message: str):
            nonlocal _message_2
            _message_2.append((time.time(), message))

        started_publisher.subscribe(callback1)
        started_publisher.subscribe(callback2)
        await started_publisher.publish("hello world")
        await started_publisher.publish("second")

        while len(_message_1) < 2 or len(_message_2) < 2:
            await asyncio.sleep(0.000001)

        assert (
            abs(_message_1[0][0] - _message_2[0][0] - 0.1) < 0.02
        ), "Messages should be processed with a delay of 0.1 seconds roughly"
        assert (
            abs(_message_2[1][0] - _message_2[0][0] - 0.1) < 0.02
        ), "Second message should be delayed because of the other blocking operation"


# ================ END Publisher ordering/blocking tests ===============

# ================= START Publisher exception tests ============
class TestPublisherException:
    @pytest.mark.asyncio
    async def test_exception_thrower(self, started_publisher):
        def exception_thrower(message: str):
            raise ValueError("This is a test exception")

        _message = None

        def callback(message: str):
            nonlocal _message
            _message = message

        started_publisher.subscribe(callback)
        started_publisher.subscribe(exception_thrower)

        await started_publisher.publish("hello world")

        await started_publisher.publish("another message")

        await asyncio.sleep(0.1)
        assert (
            _message == "another message"
        ), "Callback should still receive messages even if one broadcast_callback throws an exception"

    @pytest.mark.asyncio
    async def test_stream_subscriber_callback_exception(self, streaming_message):
        def bad(val):
            raise Exception("fail!")  # coverage for error handling

        handler = stream_subscriber(bad)
        with pytest.raises(Exception):
            await handler(streaming_message)
# ================ END Publisher exception tests ===============

# ================= START Publisher listener tests ============
class TestPublisherListener:
    @pytest.mark.asyncio
    async def test_listener_resolves_on_match(self, async_publisher):
        fut = async_publisher.listener(lambda x: x == 42)
        await async_publisher.publish(10)
        await async_publisher.publish(42)
        found = await fut
        assert found == 42


    @pytest.mark.asyncio
    async def test_listener_with_result_mapping(self, async_publisher):
        fut = async_publisher.listener(lambda x: x == 9, result_mapping=lambda x: x * 2)
        await async_publisher.publish(9)
        result = await fut
        assert result == 18


    @pytest.mark.asyncio
    async def test_listener_raises_post_shutdown(self, started_publisher):
        fut = started_publisher.listener(lambda x: x == "no")
        await started_publisher.shutdown()
        with pytest.raises(ValueError):
            await fut


    @pytest.mark.asyncio
    async def test_listener_timeout_no_message(self, async_publisher):
        fut = async_publisher.listener(lambda x: x == "never")
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(fut, timeout=0.1)

    @pytest.mark.asyncio
    async def test_listener_simple(self, async_publisher):
        _message = None

        def callback(message: str):
            nonlocal _message
            _message = message

        async_publisher.subscribe(callback)

        def message_filter(message: str) -> bool:
            return message == "hello world"

        future = async_publisher.listener(message_filter)

        await async_publisher.publish("hello world")
        result = await future

        assert result == "hello world"
        assert _message == "hello world"


    @pytest.mark.timeout(0.1)
    @pytest.mark.asyncio
    async def test_listener_many_messages(self, async_publisher):
        hw_listener = async_publisher.listener(lambda x: x == "hello world")

        am_listener = async_publisher.listener(lambda x: x == "another message")

        await async_publisher.publish("lala")
        await async_publisher.publish("hello world")
        assert await hw_listener == "hello world"
        await async_publisher.publish("another message")
        assert await am_listener == "another message"
        await async_publisher.publish("hello world")


    @pytest.mark.asyncio
    async def test_precheck_listener(self, async_publisher):
            hw_listener = async_publisher.listener(lambda x: x == "hello world")

            await async_publisher.publish("lala")

            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(hw_listener, timeout=0.1)


    @pytest.mark.asyncio
    async def test_get_listener_after_shutdown(self, async_publisher):
        hw_listener = async_publisher.listener(lambda x: x == "hello world")

        await async_publisher.publish("greenery")
        await async_publisher.shutdown()

        with pytest.raises(ValueError):
            await hw_listener  # Should raise an error since the publisher is shutdown
# ================ END Publisher listener tests ===============

# ================= START Publisher advanced tests ============
class TestPublisherSanity:
    @pytest.mark.asyncio
    async def test_is_running_and_shutdown(self, started_publisher):
        assert started_publisher.is_running() is True
        await started_publisher.shutdown()
        assert started_publisher.is_running() is False


    @pytest.mark.asyncio
    async def test_publish_after_shutdown_raises(self, started_publisher):
        await started_publisher.shutdown()
        with pytest.raises(RuntimeError):
            await started_publisher.publish("anything")

# ================ END Publisher advanced tests ===============

# ================= START Subscriber (stream_subscriber) tests ============
class TestSubscriberStream:
    @pytest.mark.asyncio
    async def test_stream_subscriber_handles_streaming_true(
        self, streaming_message, streamed_object
    ):
        results = []

        def cb(val):
            results.append(val)

        handler = stream_subscriber(cb)
        await handler(streaming_message)
        assert results == [streamed_object]


    @pytest.mark.asyncio
    async def test_stream_subscriber_skips_non_streaming(self):
        class DummyMsg:
            pass

        results = []

        def cb(val):
            results.append(val)

        handler = stream_subscriber(cb)
        await handler(DummyMsg())
        assert results == []


    @pytest.mark.asyncio
    async def test_stream_subscriber_supports_async_callbacks(
        self, streaming_message, streamed_object
    ):
        results = []

        async def cb(val):
            results.append(val)

        handler = stream_subscriber(cb)
        await handler(streaming_message)
        assert results == [streamed_object]

# ================ END Subscriber (stream_subscriber) tests ===============

# ================= START Miscellaneous corner cases ============
class TestMisc:
    @pytest.mark.asyncio
    async def test_publish_with_many_subscribers(self, async_publisher):
        order = []

        def cb1(x):
            order.append(f"A{x}")

        def cb2(x):
            order.append(f"B{x}")

        def cb3(x):
            order.append(f"C{x}")

        async_publisher.subscribe(cb1)
        async_publisher.subscribe(cb2)
        async_publisher.subscribe(cb3)
        for n in range(3):
            await async_publisher.publish(n)
        for _ in range(10):
            if len(order) == 9:
                break
            await asyncio.sleep(0.02)
        expected = set([f"{l}{n}" for l in "ABC" for n in range(3)])
        assert set(order) == expected


    @pytest.mark.asyncio
    async def test_subscribe_unsubscribe_multiple(self, started_publisher):
        got = []
        ids = []
        for i in range(3):

            def cb(x, lab=i):
                got.append((lab, x))

            sid = started_publisher.subscribe(cb)
            ids.append(sid)
        for sid in ids:
            started_publisher.unsubscribe(sid)
        await started_publisher.publish("noop")
        await asyncio.sleep(0.01)
        # No callbacks should run after all are removed
        assert got == []


    @pytest.mark.asyncio
    async def test_subscriber_autonames_are_unique(self, started_publisher):
        def cb1(x):
            pass

        def cb2(x):
            pass

        s1_id = started_publisher.subscribe(cb1)
        s2_id = started_publisher.subscribe(cb2)
        assert s1_id != s2_id


    @pytest.mark.asyncio
    async def test_double_shutdown_ok(self, started_publisher):
        await started_publisher.shutdown()
        # Should not error
        await started_publisher.shutdown()


    @pytest.mark.asyncio
    async def test_subscriber_id_uniqueness(self, async_publisher):
        ids = []
        for i in range(5):

            async def cb(x):
                pass

            sid = async_publisher.subscribe(cb)
            ids.append(sid)
        assert len(set(ids)) == 5
# ================ END Miscellaneous corner cases ===============
