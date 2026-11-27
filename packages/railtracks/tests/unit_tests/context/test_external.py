import copy
import pickle
import threading
import warnings
from typing import Callable

import pytest
from railtracks.context.external import (
    ExternalContext,
    MutableExternalContext,
)


# ============ START Basic Access Tests ===============
def test_simple_empty():
    context = MutableExternalContext()

    with pytest.raises(KeyError):
        context.get("test_key")

    context.put("test_key", "test_value")


def test_simple_load_in():
    context = MutableExternalContext()
    context.update({"test_key": "test_value"})

    assert context.get("test_key") == "test_value"
    assert context.get("non_existent_key", default="default_value") == "default_value"

    with pytest.raises(KeyError):
        context.get("non_existent_key")

    context.put("test_key", "new_value")


def test_double_load_in():
    context = MutableExternalContext()
    context.update({"test_key": "test_value"})

    context.update({"another_key": "another_value"})

    assert context.get("test_key") == "test_value"
    assert context.get("another_key") == "another_value"


# ============ END Basic Access Tests ===============


# ============ START Dict-Like Behavior Tests ===============
def test_setitem_and_getitem():
    context = MutableExternalContext()
    context["foo"] = "bar"
    assert context["foo"] == "bar"


# ============ END Dict-Like Behavior Tests ===============


# ============ START Update/Overwrite Tests ===============
def test_update_overwrites_but_does_not_delete():
    context = MutableExternalContext({"a": 1, "b": 2})
    context.update({"a": 10, "c": 3})
    assert context.get("a") == 10
    assert context.get("b") == 2
    assert context.get("c") == 3


# ============ END Update/Overwrite Tests ===============


# ============ START Delete Tests ===============
def test_delete_from_context():
    context = MutableExternalContext()
    context.update({"a": 1})
    assert context.get("a") == 1
    context.delete("a")
    with pytest.raises(KeyError):
        context.get("a")


# ============ END Delete Tests ===============


# ============ START Keys Tests ===============
def test_keys_empty_context():
    context = MutableExternalContext()
    keys = context.keys()
    assert len(keys) == 0


def test_keys_with_data():
    context = MutableExternalContext({"a": 1, "b": 2})
    keys = context.keys()
    assert set(keys) == {"a", "b"}


def test_keys_after_modifications():
    context = MutableExternalContext({"a": 1})

    # Add a key
    context.put("b", 2)
    keys = context.keys()
    assert set(keys) == {"a", "b"}

    # Delete a key
    context.delete("a")
    keys = context.keys()
    assert set(keys) == {"b"}

    # Update with new keys
    context.update({"c": 3, "d": 4})
    keys = context.keys()
    assert set(keys) == {"b", "c", "d"}


# ============ END Keys Tests ===============


# ============ START Initialization Tests ===============
def test_init_with_input_dict():
    d = {"x": 42}
    context = MutableExternalContext(d)
    assert context.get("x") == 42
    # Changing the original dict should reflect in context (since it's not copied)
    d["y"] = 99
    assert context.get("y") == 99


# ============ END Initialization Tests ===============


# ============ START Error Handling Tests ===============
def test_get_raises_keyerror_when_default_is_none():
    context = MutableExternalContext()
    with pytest.raises(KeyError):
        context.get("missing")


# ============ END Error Handling Tests ===============


# ============ START Items Tests ===============
def test_items_returns_every_pair():
    context = MutableExternalContext({"a": 1, "b": 2})
    assert dict(context.items()) == {"a": 1, "b": 2}


def test_items_is_empty_for_an_empty_context():
    assert dict(MutableExternalContext().items()) == {}


def test_items_is_a_copy_not_a_live_view():
    context = MutableExternalContext({"a": 1})
    items = context.items()
    context.put("b", 2)
    assert dict(items) == {"a": 1}


# ============ END Items Tests ===============


# ============ START Keys Snapshot Tests ===============
def test_keys_is_a_copy_not_a_live_view():
    context = MutableExternalContext({"a": 1})
    keys = context.keys()
    context.put("b", 2)
    assert set(keys) == {"a"}


# ============ END Keys Snapshot Tests ===============


# ============ START Mutate Tests ===============
def test_mutate_existing_key():
    context = MutableExternalContext({"count": 5})
    result = context.mutate("count", lambda n: n + 1)
    assert result == 6
    assert context.get("count") == 6


def test_mutate_missing_key_with_default():
    context = MutableExternalContext()
    assert context.mutate("count", lambda n: n + 1, default=0) == 1
    assert context.get("count") == 1


def test_mutate_missing_key_with_none_default():
    context = MutableExternalContext()
    result = context.mutate(
        "items", lambda xs: [] if xs is None else [*xs, "a"], default=None
    )
    assert result == []
    assert context.get("items") == []


def test_mutate_missing_key_without_default_raises():
    context = MutableExternalContext()
    with pytest.raises(KeyError):
        context.mutate("missing", lambda x: x)


def test_mutate_reentrant_read_does_not_deadlock():
    context = MutableExternalContext({"step": 2, "count": 10})
    result = context.mutate("count", lambda n: n + context.get("step"))
    assert result == 12
    assert context.get("count") == 12


def test_mutate_callback_error_leaves_store_unchanged():
    context = MutableExternalContext({"count": 5})

    def boom(_):
        raise ValueError("fail")

    with pytest.raises(ValueError, match="fail"):
        context.mutate("count", boom)

    assert context.get("count") == 5

    with pytest.raises(ValueError, match="fail"):
        context.mutate("absent", boom, default=0)

    with pytest.raises(KeyError):
        context.get("absent")


def test_mutate_rejects_async_callback():
    context = MutableExternalContext({"count": 1})

    async def inc(n):
        return n + 1

    with pytest.raises(TypeError, match="synchronous"):
        context.mutate("count", inc)

    assert context.get("count") == 1


def test_mutate_rejects_returned_coroutine_without_warning():
    context = MutableExternalContext({"count": 1})

    async def inc(n):
        return n + 1

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        with pytest.raises(TypeError, match="synchronous"):
            context.mutate("count", lambda n: inc(n))

    assert not any("was never awaited" in str(w.message) for w in caught)
    assert context.get("count") == 1


def test_external_context_subclass_inherits_default_mutate():
    class DictBackedContext(ExternalContext):
        def __init__(self):
            self._data = {"x": 1}

        def update(self, data):
            self._data.update(data)

        def get(self, key, *, default=None):
            if key not in self._data:
                if default is not None:
                    return default
                raise KeyError(key)
            return self._data[key]

        def put(self, key, value):
            self._data[key] = value

        def delete(self, key):
            del self._data[key]

        def keys(self):
            return self._data.keys()

        def items(self):
            return self._data.items()

    ctx = DictBackedContext()
    assert ctx.mutate("x", lambda v: v + 2) == 3
    assert ctx.mutate("y", lambda v: v + 1, default=10) == 11
    with pytest.raises(KeyError):
        ctx.mutate("missing", lambda v: v)


# ============ END Mutate Tests ===============


# ============ START Serialization Tests ===============
def test_pickle_and_deepcopy_preserve_working_lock():
    context = MutableExternalContext({"count": 1})

    unpickled = pickle.loads(pickle.dumps(context))
    assert unpickled.mutate("count", lambda n: n + 1) == 2

    cloned = copy.deepcopy(context)
    assert cloned.mutate("count", lambda n: n + 5) == 6
    assert context.get("count") == 1


# ============ END Serialization Tests ===============


# ============ START Concurrency Tests ===============
def test_concurrent_mutate_has_no_lost_updates():
    context = MutableExternalContext({"n": 0})
    num_threads = 16
    increments_per_thread = 200
    barrier = threading.Barrier(num_threads)
    errors: list[BaseException] = []

    def worker():
        try:
            barrier.wait()
            for _ in range(increments_per_thread):
                context.mutate("n", lambda x: x + 1)
        except BaseException as exc:  # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert context.get("n") == num_threads * increments_per_thread


def _run_concurrent_rw(
    num_writers: int,
    writer_step: Callable[[int], None],
    num_readers: int,
    reader_step: Callable[[], None],
) -> None:
    stop = threading.Event()
    errors: list[BaseException] = []

    def run_writer(tid: int) -> None:
        try:
            writer_step(tid)
        except BaseException as exc:  # pragma: no cover
            errors.append(exc)

    def run_reader() -> None:
        try:
            while not stop.is_set():
                reader_step()
        except BaseException as exc:  # pragma: no cover
            errors.append(exc)

    readers = [threading.Thread(target=run_reader) for _ in range(num_readers)]
    writers = [
        threading.Thread(target=run_writer, args=(tid,)) for tid in range(num_writers)
    ]
    for r in readers:
        r.start()
    for w in writers:
        w.start()
    for w in writers:
        w.join()
    stop.set()
    for r in readers:
        r.join()
    assert errors == []


def test_concurrent_keys_and_items_never_raise_during_mutations():
    context = MutableExternalContext({"seed": 0})

    def writer(tid: int) -> None:
        for i in range(300):
            key = f"k_{tid}_{i % 10}"
            context.put(key, i)
            if i % 2 == 0:
                context.delete(key)

    def reader() -> None:
        list(context.keys())
        list(context.items())

    _run_concurrent_rw(4, writer, 4, reader)


def test_concurrent_update_and_items_preserve_multi_key_invariant():
    context = MutableExternalContext({"a": 0, "b": 0})

    def writer(_tid: int) -> None:
        for i in range(1, 500):
            context.update({"a": i, "b": i})

    def reader() -> None:
        snap = dict(context.items())
        assert snap["a"] == snap["b"]

    _run_concurrent_rw(2, writer, 4, reader)


# ============ END Concurrency Tests ===============
