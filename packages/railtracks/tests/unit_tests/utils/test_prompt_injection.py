import railtracks.llm.prompt_injection_utils as prompt_injection_utils
from railtracks.llm.prompt_injection_utils import KeyOnlyFormatter, ValueDict

from railtracks.llm.message import Role
from railtracks.utils import prompt_injection
from railtracks.llm import Message, MessageHistory, UserMessage, SystemMessage


# ================= START KeyOnlyFormatter tests ============

def test_formatter_uses_only_kwargs():
    f = KeyOnlyFormatter()
    formatted = f.format("Hello, {name}", name="Test")
    assert formatted == "Hello, Test"

def test_formatter_missing_key_returns_placeholder():
    f = KeyOnlyFormatter()
    formatted = f.format("Hello, {name}")
    assert formatted == "Hello, {name}"

def test_formatter_treats_unknown_attribute_like_field_as_literal():
    f = KeyOnlyFormatter()
    formatted = f.format("We define the set {x. some property} and keep it.")
    assert formatted == "We define the set {x. some property} and keep it."

def test_formatter_treats_json_like_content_as_literal():
    f = KeyOnlyFormatter()
    formatted = f.format('Payload: {"items": [1, 2], "ok": true}')
    assert formatted == 'Payload: {"items": [1, 2], "ok": true}'

def test_formatter_treats_unbalanced_braces_as_literal():
    f = KeyOnlyFormatter()
    formatted = f.format("Start {x and end }")
    assert formatted == "Start {x and end }"

def test_formatter_uses_getitem_for_lookup_only_mappings():
    class LookupOnlyDict(dict):
        def __getitem__(self, key):
            if key == "name":
                return "Alice"
            raise KeyError(key)

    f = KeyOnlyFormatter()
    formatted = f.vformat("Hello, {name}", (), LookupOnlyDict())
    assert formatted == "Hello, Alice"

# ================ END KeyOnlyFormatter tests ===============


# ================= START ValueDict tests ====================

def test_valuedict_returns_value_if_exists():
    d = prompt_injection.ValueDict(name="Bob")
    assert d["name"] == "Bob"

def test_valuedict_missing_returns_placeholder():
    d = prompt_injection.ValueDict()
    assert d["missing"] == "{missing}"

# ================ END ValueDict tests =======================


# ================= START inject_values tests ================

def test_inject_values_injects_value():
    smsg = SystemMessage(content="System says {system_info}", inject_prompt=True)
    msg = UserMessage(content="Hello, {name}!", inject_prompt=True)
    history = MessageHistory([smsg, msg])
    value_dict = ValueDict({"name": "Alice", "system_info": "All systems operational"})

    result = prompt_injection.inject_values(history, value_dict)
    assert result[0].content == "System says All systems operational"
    assert result[0].inject_prompt is False
    assert result[1].content == "Hello, Alice!"
    assert result[1].inject_prompt is False

def test_inject_values_ignores_no_inject():
    msg = Message(role=Role.user, content="Hello!", inject_prompt=False)
    history = MessageHistory([msg])
    value_dict = ValueDict({"name": "Alice"})

    result = prompt_injection.inject_values(history, value_dict)
    assert result[0].content == "Hello!"
    assert result[0].inject_prompt is False

def test_inject_values_ignores_non_string_content():
    msg = Message(role=Role.user, content=12345, inject_prompt=True)
    history = MessageHistory([msg])
    value_dict = ValueDict({"name": "Alice"})

    result = prompt_injection.inject_values(history, value_dict)
    assert result[0].content == 12345

def test_inject_values_preserves_literal_brace_content():
    msg = UserMessage(
        content='We define {x. some property}; JSON: {"items": [1, 2]}.',
        inject_prompt=True,
    )
    history = MessageHistory([msg])
    value_dict = ValueDict({"name": "Alice"})

    result = prompt_injection.inject_values(history, value_dict)
    assert result[0].content == 'We define {x. some property}; JSON: {"items": [1, 2]}.'
    assert result[0].inject_prompt is False

def test_inject_values_catches_valueerror(monkeypatch):
    # Patch fill_prompt to throw ValueError
    msg = Message(role=Role.user, content="Hello, {name}!", inject_prompt=True)
    history = MessageHistory([msg])
    value_dict = ValueDict({"name": "Alice"})

    monkeypatch.setattr(UserMessage, "fill_prompt", lambda content, vd: (_ for _ in ()).throw(ValueError("forced")))

    # Should not raise, and content should be unchanged
    result = prompt_injection.inject_values(history, value_dict)
    assert result[0].content == "Hello, {name}!"

# ================ END inject_values tests ==================
