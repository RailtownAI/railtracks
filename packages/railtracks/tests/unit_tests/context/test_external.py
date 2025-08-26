import pytest
from railtracks.context.external import (
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
