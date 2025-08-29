import pytest
import railtracks as rt
from railtracks import function_node
from railtracks.context import delete, get, keys, put, update
from railtracks.interaction._call import call


def set_context():
    put("test_key", "test_value")


def retrieve_context():
    return get("test_key", default="default_value")


async def context_flow():
    await call(function_node(set_context))
    return await call(function_node(retrieve_context))


@pytest.mark.asyncio
async def test_put_context():
    context_node = function_node(context_flow)
    with rt.Session():
        result = await rt.call(context_node)

    assert result == "test_value"


def test_update_and_delete_context():
    with rt.Session():
        put("key2", "value2")
        update({"key": "value"})

        assert get("key") == "value"

        delete("key")
        with pytest.raises(KeyError):
            get("key")

        # Ensure update does not delete existing keys
        assert get("key2") == "value2"


def test_context_addition():
    with rt.Session(context={"hello world": "test_value"}):
        rt.context.put("test_key", "duo")
        assert rt.context.get("test_key") == "duo"
        assert rt.context.get("hello world") == "test_value"


def test_context_replacement():
    with rt.Session(context={"hello world": "test_value"}):
        rt.context.put("hello world", "new_value")
        assert rt.context.get("hello world") == "new_value"

        with pytest.raises(KeyError):
            rt.context.get("non_existent_key")


def test_multiple_runners():
    with rt.Session(context={"key1": "value1"}):
        assert rt.context.get("key1") == "value1"
        rt.context.put("key2", "updated_value1")
        rt.context.put("key3", "value3")
        assert rt.context.get("key2") == "updated_value1"
        assert rt.context.get("key3") == "value3"

    with rt.Session(context={"key2": "value2"}):
        assert rt.context.get("key2") == "value2"

        # Ensure that context from the first runner is not accessible in the second
        with pytest.raises(KeyError):
            rt.context.get("key1")

        with pytest.raises(KeyError):
            rt.context.get("key3")

    with rt.Session():
        # Ensure that the context is empty in a new runner
        with pytest.raises(KeyError):
            rt.context.get("key1")
        with pytest.raises(KeyError):
            rt.context.get("key2")
        with pytest.raises(KeyError):
            rt.context.get("key3")


def test_keys_empty_context():
    with rt.Session():
        context_keys = keys()
        assert len(context_keys) == 0


def test_keys_with_initial_context():
    with rt.Session(context={"key1": "value1", "key2": "value2"}):
        context_keys = keys()
        assert set(context_keys) == {"key1", "key2"}


def test_keys_after_modifications():
    with rt.Session(context={"initial": "value"}):
        # Initial state
        context_keys = keys()
        assert set(context_keys) == {"initial"}

        # Add keys
        put("new_key", "new_value")
        update({"another": "another_value"})
        context_keys = keys()
        assert set(context_keys) == {"initial", "new_key", "another"}

        # Delete a key
        delete("initial")
        context_keys = keys()
        assert set(context_keys) == {"new_key", "another"}


@pytest.mark.asyncio
async def test_keys_across_function_calls():
    def get_context_keys():
        return list(keys())

    with rt.Session(context={"test": "value"}):
        put("runtime", "data")

        # Test that keys() works inside function nodes
        keys_node = function_node(get_context_keys)
        result = await rt.call(keys_node)
        assert set(result) == {"test", "runtime"}
