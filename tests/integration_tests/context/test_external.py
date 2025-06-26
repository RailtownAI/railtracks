import pytest
import requestcompletion as rc
from requestcompletion.context import put, get
from requestcompletion.nodes.library import from_function
from requestcompletion.interaction.call import call


def set_context():
    put("test_key", "test_value")


def retrieve_context():
    return get("test_key", default="default_value")


async def context_flow():
    await call(from_function(set_context))
    return await call(from_function(retrieve_context))


def test_put_context():
    context_node = from_function(context_flow)
    with rc.Runner() as runner:
        result = runner.run_sync(context_node)

    assert result.answer == "test_value"


def test_context_addition():
    with rc.Runner(context={"hello world": "test_value"}):
        rc.context.put("test_key", "duo")
        assert rc.context.get("test_key") == "duo"
        assert rc.context.get("hello world") == "test_value"

def test_context_replacement():
    with rc.Runner(context={"hello world": "test_value"}):
        rc.context.put("hello world", "new_value")
        assert rc.context.get("hello world") == "new_value"

        with pytest.raises(KeyError):
            rc.context.get("non_existent_key")

def test_multiple_runners():
    with rc.Runner(context={"key1": "value1"}):
        assert rc.context.get("key1") == "value1"
        rc.context.put("key2", "updated_value1")
        rc.context.put("key3", "value3")
        assert rc.context.get("key2") == "updated_value1"
        assert rc.context.get("key3") == "value3"


    with rc.Runner(context={"key2": "value2"}):

        assert rc.context.get("key2") == "value2"

        # Ensure that context from the first runner is not accessible in the second
        with pytest.raises(KeyError):
            rc.context.get("key1")

        with pytest.raises(KeyError):
            rc.context.get("key3")

    with rc.Runner():
        # Ensure that the context is empty in a new runner
        with pytest.raises(KeyError):
            rc.context.get("key1")
        with pytest.raises(KeyError):
            rc.context.get("key2")
        with pytest.raises(KeyError):
            rc.context.get("key3")




