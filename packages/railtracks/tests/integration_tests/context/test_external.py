import pytest
import railtracks as rt
from railtracks.context import put, get
from railtracks import function_node
from railtracks.interaction.call import call


def set_context():
    put("test_key", "test_value")


def retrieve_context():
    return get("test_key", default="default_value")


async def context_flow():
    await call(function_node(set_context))
    return await call(function_node(retrieve_context))


def test_put_context():
    context_node = function_node(context_flow)
    with rt.Session():
        result = rt.call_sync(context_node)

    assert result == "test_value"


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




