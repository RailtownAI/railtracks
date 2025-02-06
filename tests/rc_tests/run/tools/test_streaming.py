import threading
import time

from requestcompletion.run.tools.stream import (
    DataStream,
    Subscriber,
)


def test_simple_handler():
    class Handler(Subscriber[str]):
        def __init__(self):
            self.last_data = None

        def handle(self, item: str):
            self.last_data = item

    h = Handler()
    ds = DataStream[str](subscribers=[h])
    ds.publish("test")
    ds.stop()
    assert h.last_data == "test"


def test_multiple_data():
    class Handler(Subscriber[str]):
        def __init__(self):
            self._lock = threading.Lock()
            self.data = []

        def handle(self, item: str):
            with self._lock:
                self.data.append(item)

    h = Handler()
    ds = DataStream[str](subscribers=[h])
    ds.publish("test")
    ds.publish("test2")
    ds.stop()
    assert h.data == ["test", "test2"]


def test_huge_data():
    class Handler(Subscriber[str]):
        def __init__(self):
            self._lock = threading.Lock()
            self.data = []

        def handle(self, item: str):
            with self._lock:
                self.data.append(item)

    h = Handler()
    ds = DataStream[str](subscribers=[h])
    for i in range(1000):
        ds.publish(f"test{i}")
    ds.stop()
    assert h.data == [f"test{i}" for i in range(1000)]


def test_force_close():
    class Handler(Subscriber[str]):
        def __init__(self):
            self._lock = threading.Lock()
            self.data = []

        def handle(self, item: str):
            with self._lock:
                self.data.append(item)

    h = Handler()
    ds = DataStream[str](subscribers=[h])
    for i in range(1000):
        ds.publish(f"test{i}")
    time.sleep(0.1)
    ds.stop(force=True)
    for i in range(1000):
        if len(h.data) == 0:
            assert i > 5
            break

        h.data.pop(0)


def test_multiple_subs():
    class Handler(Subscriber[str]):
        def __init__(self):
            self._lock = threading.Lock()
            self.data = []

        def handle(self, item: str):
            with self._lock:
                self.data.append(item)

    class Handler2(Subscriber[str]):
        def __init__(self):
            self.last_data = None

        def handle(self, item: str):
            self.last_data = item

    h = Handler()
    h2 = Handler2()
    ds = DataStream[str](subscribers=[h, h2])
    ds.publish("test")
    ds.publish("test2")

    ds.stop()

    assert h.data == ["test", "test2"]
    assert h2.last_data == "test2"


def test_add_after_close():
    class Handler(Subscriber[str]):
        def __init__(self):
            self._lock = threading.Lock()
            self.data = []

        def handle(self, item: str):
            with self._lock:
                self.data.append(item)

    h = Handler()
    ds = DataStream[str]([h])
    ds.publish("test")
    ds.stop()
    ds.publish("test2")
    assert h.data == ["test"]


def test_no_subs():
    ds = DataStream[str]()
    ds.publish("test")
    ds.stop()
